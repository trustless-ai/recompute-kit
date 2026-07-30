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
import sys, json, hashlib, os

def jcs(v):     # receiptos-c14n: recursive sorted-key, compact, non-ASCII literal
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def compact(v): # positional (NIP-01 array is not key-sorted)
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)

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
    sys.exit(1 if fails else 0)
