#!/usr/bin/env python3
"""pq_key_binding.v0 — deep-artifact recompute lane (hash + merkle + on-chain consistency).

The suite's `*-vectors.json` files run the resolution cases. The three DEEP artifacts —
`pq-key-binding-v0.per-agent-anchor.json`, `.rotation.json`, `.revocation.json` — carry the real
statements, the Merkle proof, the on-chain anchor and the PQ signatures the spec references, but
were in NO manifest check, so `run_conformance` executed them in nothing. A claim executed by
nothing has no failure mode. This gate recomputes every HASH-checkable claim each artifact makes
and fails (exit 1) on any tamper.

Lane boundary, stated not skipped: the ML-DSA SIGNATURE legs (rotation continuity/companion,
revocation pq_authorization) are NOT verified in this offline hash lane — they are verified live in
the gateway with real signatures (`/pq/agent/:registry/:id/rotation/selftest` and
`/pq/agent/:registry/:id/enforce/selftest`). This gate PRINTS that boundary as a deferred line so a
reader sees exactly what it did and did not cover; exit 0 means "the hash/merkle/anchor claims hold",
never "the signatures verified".
"""
import sys, json, hashlib, os


def jcs(v):  # receiptos-c14n / RFC 8785: recursive sorted-key, compact, non-ASCII literal
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def cc_of(statement):
    return hashlib.sha256(jcs(statement).encode()).hexdigest()


def fold_merkle(leaf_hex, proof_hex):
    node = bytes.fromhex(leaf_hex)
    for p in proof_hex:
        pb = bytes.fromhex(p)
        node = hashlib.sha256(node + pb).digest() if node <= pb else hashlib.sha256(pb + node).digest()
    return node.hex()


def check_per_agent_anchor(d):
    checks = [("content_address", cc_of(d["statement"]) == d["canonical_content_sha256"])]
    folded = fold_merkle(d["canonical_content_sha256"], d["merkle_proof"])
    checks.append(("merkle_fold_to_root", folded == d["merkle_root"]))
    # offline consistency of the on-chain record with the folded root (the live tx fetch — that the
    # b5c645bd calldata carries this root — is the gateway's job, not this offline lane's).
    checks.append(("anchor_records_eq_root", d["onchain_anchor"]["records"] == d["merkle_root"]))
    deferred = []  # per-agent-anchor is fully covered offline (hash + merkle + anchor consistency)
    return checks, deferred


def check_rotation(d):
    checks = [("content_address", cc_of(d["statement"]) == d["canonical_content_sha256"])]
    if "canonical_content" in d:  # the pinned canonical string must itself be JCS(statement)
        checks.append(("canonical_content_is_jcs_of_statement", d["canonical_content"] == jcs(d["statement"])))
    deferred = ["continuity_signature (ML-DSA)", "pq_companion_signature (ML-DSA)"]
    return checks, deferred


def check_revocation(d):
    checks = []
    for part in ("binding", "revocation"):
        checks.append((f"{part}.content_address", cc_of(d[part]["statement"]) == d[part]["canonical_content_sha256"]))
    deferred = ["revocation.pq_authorization (ML-DSA)"]
    return checks, deferred


DISPATCH = {
    "pq-key-binding-v0.per-agent-anchor.json": check_per_agent_anchor,
    "pq-key-binding-v0.rotation.json": check_rotation,
    "pq-key-binding-v0.revocation.json": check_revocation,
}


def run(path):
    name = os.path.basename(path)
    fn = DISPATCH.get(name)
    if fn is None:
        print(f"BAD unknown deep artifact: {name}")
        return 1
    checks, deferred = fn(json.load(open(path)))
    fails = 0
    for cname, ok in checks:
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {name} :: {cname}")
    if deferred:
        print(f"    deferred (signature lane — verified live in gateway /pq/*/selftest, not this hash lane): {', '.join(deferred)}")
    print(f"{len(checks) - fails}/{len(checks)} hash-recompute claims reproduced")
    return fails


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    sys.exit(1 if run(arg or os.path.join(here, "pq-key-binding-v0.per-agent-anchor.json")) else 0)
