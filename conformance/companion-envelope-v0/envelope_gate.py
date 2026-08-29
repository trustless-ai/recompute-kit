#!/usr/bin/env python3
"""companion-envelope.v0 — recompute the envelope that commits a verdict to its companion.

  verdict_core_cc = sha256(JCS(core))                                  (what the companion signs)
  companion       = {signed_digest: verdict_core_cc, pq_pubkey, ml_dsa_signature}
  companion_cc    = sha256(JCS(companion))
  envelope        = {schema, verdict_core_cc, companion_cc}            (envelope_cc commits to both)

A companion whose recorded content_address is not this verdict_core_cc did not sign this verdict, so it
is NOT committed: companion_cc is null and companion_status is "unresolved". An unresolvable companion is
UNRESOLVED, never false. Byte-for-byte identical to the gateway's TS producer (pqAgent.ts companionEnvelope).
"""
import sys, json, hashlib, os

def jcs(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()

def attestation_cc(f):
    return sha(jcs({
        "raw_input_hash": f.get("raw_input_hash"), "sanitization_pipeline_hash": f.get("sanitization_pipeline_hash"),
        "input_hash": f.get("input_hash"), "output_hash": f.get("output_hash"), "manifest_hash": f.get("manifest_hash"),
        "agent_id": f.get("agent_id"), "registry": (f.get("registry") or "").lower() or None,
    }))

def companion_envelope(core, companion):
    vcc = attestation_cc(core)
    cc, status = None, "unresolved"
    # A committed companion MUST record the exact core it signed: content_address PRESENT and == verdict_core_cc.
    # Accepting an absent content_address (and manufacturing signed_digest = verdict_core_cc) would fabricate the
    # binding without evidence — a companion that never named this core would read as committed. (Pavlo, #32.)
    belongs = bool(companion and companion.get("pq_pubkey") and companion.get("signature_hex") and
                   companion.get("content_address") and companion["content_address"] == vcc)
    if belongs:
        obj = {"signed_digest": vcc, "pq_pubkey": companion["pq_pubkey"], "ml_dsa_signature": companion["signature_hex"]}
        cc, status = sha(jcs(obj)), "committed"
    envelope = {"schema": "companion-envelope.v0", "verdict_core_cc": vcc, "companion_cc": cc}
    return {"verdict_core_cc": vcc, "companion_cc": cc, "companion_status": status, "envelope_cc": sha(jcs(envelope))}

def run(path):
    doc = json.load(open(path))
    fails = 0
    for v in doc["vectors"]:
        got, exp = companion_envelope(v["core"], v.get("companion")), v["expect"]
        ok = all(got[k] == exp[k] for k in ("verdict_core_cc", "companion_cc", "companion_status", "envelope_cc"))
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {v['name']:<32} status={got['companion_status']:<10} companion_cc={str(got['companion_cc'])[:12]}")
    print(f"{len(doc['vectors']) - fails}/{len(doc['vectors'])} vectors reproduced")
    return fails

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    sys.exit(1 if run(arg or os.path.join(here, "companion-envelope-v0.vectors.json")) else 0)
