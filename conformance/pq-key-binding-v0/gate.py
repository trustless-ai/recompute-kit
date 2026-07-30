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
    st, c = vec["statement"], vec["carrier"]
    content = jcs(st)
    cc = hashlib.sha256(content.encode()).hexdigest()
    ser = compact([0, c["pubkey"], c["created_at"], c["kind"], c["tags"], content])
    eid = hashlib.sha256(ser.encode()).hexdigest()
    return {"canonical_content_sha256": cc, "event_id": eid}

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
        print(f"{'OK ' if ok else 'BAD'} {v['name']:<38} cc={got['canonical_content_sha256'][:12]}… id={got['event_id'][:12]}…")
    print(f"{len(fx['vectors']) - fails}/{len(fx['vectors'])} reproduced")
    sys.exit(1 if fails else 0)
