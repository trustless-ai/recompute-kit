#!/usr/bin/env python3
"""pq_key_binding.v0 — recompute the binding's self-verifying content-address (hash-only lane).

The binding earns trust by re-derivation, not by what an endpoint serves: the verifier recomputes
  canonical_content        = JCS(statement)                       # receiptos-c14n / RFC-8785
  canonical_content_sha256 = sha256(canonical_content)
  event_id                 = sha256(compact-JSON [0, pubkey, created_at, kind, tags, canonical_content])
and checks them against the claimed values. The manifest (verifier-keys.json) is discovery only.
The BIP-340 Schnorr + ML-DSA/SLH-DSA signature checks are the separate deep lane (need secp256k1 /
dilithium libs); this suite pins the content-address that BOTH signatures cover.

Adapter contract: fixture JSON on stdin (--grade) -> {name: result} on stdout.
"""
import sys, json, hashlib, os, re

def jcs(v):     # receiptos-c14n: recursive sorted-key, compact, non-ASCII literal
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def compact(v): # positional (NIP-01 array is not key-sorted)
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)

def _hex_tokens(text, minlen=8):   # hex runs >= minlen (digest-style citations, not short 4-char elisions)
    return set(m.group(0).lower() for m in re.finditer(r"[0-9a-fA-F]{%d,}" % minlen, text))

def lint_spec(here):
    """Pavlo's failure class (2026-07-30): a pinned spec can cite a digest NO current vector produces
    (e.g. the stale 273f7b0e). Hash-pinning the spec proves the prose is *unaltered*, never *correct*.
    So verify structurally: every hex digest/prefix the spec cites MUST resolve to a current pinned
    artifact — a hex string present in the vectors file (cc / event_id / pubkey / anchor tx / contract)."""
    spec_p = os.path.join(here, "pq-key-binding-v0.spec.md")
    vec_p  = os.path.join(here, "pq-key-binding-v0.vectors.json")
    if not os.path.exists(spec_p):
        return 0
    universe = _hex_tokens(open(vec_p).read())
    cited    = _hex_tokens(open(spec_p).read())
    orphans  = [t for t in cited if not any(u.startswith(t) or t.startswith(u) for u in universe)]
    for t in sorted(orphans):
        print(f"SPEC-ORPHAN  {t[:16]}…  cited in spec but resolves to NO current vector/artifact")
    if not orphans:
        print(f"spec-lint OK — all {len(cited)} cited digests resolve to a current pinned artifact")
    return len(orphans)

def recompute(vec):
    st = vec["statement"]
    content = jcs(st)
    out = {"canonical_content_sha256": hashlib.sha256(content.encode()).hexdigest()}
    c = vec.get("carrier")   # optional: a NIP-01 carrier (Nostr). Absent for on-chain-anchored bindings.
    if c:
        ser = compact([0, c["pubkey"], c["created_at"], c["kind"], c["tags"], content])
        out["event_id"] = hashlib.sha256(ser.encode()).hexdigest()
    return out

if __name__ == "__main__":
    if "--grade" in sys.argv:
        fx = json.load(sys.stdin)
        print(json.dumps({v["name"]: recompute(v) for v in fx["vectors"]}))
        sys.exit(0)
    here = os.path.dirname(os.path.abspath(__file__))
    fx = json.load(open(os.path.join(here, "pq-key-binding-v0.vectors.json")))
    fails = 0
    for v in fx["vectors"]:
        got, exp = recompute(v), v["expected"]
        ok = got == exp
        fails += not ok
        idp = f" id={got['event_id'][:12]}…" if "event_id" in got else " (on-chain-anchored, no NIP-01 carrier)"
        print(f"{'OK ' if ok else 'BAD'} {v['name']:<38} cc={got['canonical_content_sha256'][:12]}…{idp}")
    print(f"{len(fx['vectors']) - fails}/{len(fx['vectors'])} reproduced")
    orphans = lint_spec(here)   # Pavlo's failure class: no spec-cited digest may be an orphan
    sys.exit(1 if (fails or orphans) else 0)
