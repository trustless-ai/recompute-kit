#!/usr/bin/env python3
"""verdict-profile-binding.v0 — recompute whether a resolver's verdict actually COMMITS to the
verification profile it resolved under.

The resolution end of the profile-commitment loop. profile-amendment-v0 decides which profile is
effective (the amendment end); this decides whether the resolver signed a verdict that carries that
exact effective_profile_commitment INSIDE its signed preimage, so "I resolved under this profile" is
attested and recomputable, not a side-channel reference. Together they are Pavlo's invariant end to end:

    profile_transition(task).effective_profile_commitment == verdict.core.effective_profile_commitment

  verdict_core   = { ...verdict fields..., effective_profile_commitment }   (profile is IN the core)
  verdict_core_cc = sha256(JCS(verdict_core))                               (what the resolver signs)
  resolver_sig    = { signed_digest, pubkey }                              (signed_digest MUST == verdict_core_cc)

A verdict is BOUND to its profile only if, together:
  (1) its core carries effective_profile_commitment present AND == the task's authorized
      effective_profile_commitment (it resolved under the profile that was actually in force), and
  (2) the resolver signed THIS core: signed_digest present AND == verdict_core_cc.
Otherwise resolution_status is "unresolved" and bound_profile_commitment is null: a verdict that omits
the profile, names a different one, or whose signature is over some other core is NOT certified. Same
UNRESOLVED-never-false, fail-closed discipline as companion-envelope-v0 and profile-amendment-v0.

This checks the binding, not signature cryptography: the resolver signature is "over this core" iff
signed_digest == verdict_core_cc, exactly as companion-envelope checks content_address == verdict_core_cc.
ECDSA / ML-DSA validity rides the separate signature lane.
"""
import sys, json, hashlib, os

def jcs(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()

def verdict_binding(v):
    core = v["verdict_core"]
    task_effective = v["task_effective_profile_commitment"]
    resolver = v.get("resolver_sig")

    verdict_core_cc = sha(jcs(core))
    core_profile = core.get("effective_profile_commitment")

    # (1) the verdict resolved under the profile actually in force: present AND == the task's authorized one.
    profile_bound = bool(core_profile is not None and core_profile == task_effective)
    # (2) the resolver signed THIS core (not some other verdict).
    signed_here = bool(resolver and resolver.get("signed_digest")
                       and resolver["signed_digest"] == verdict_core_cc)

    bound = bool(profile_bound and signed_here)
    status = "bound" if bound else "unresolved"
    # fail closed: only certify the profile commitment when the verdict both carries it and is signed over it.
    bound_profile_commitment = core_profile if bound else None
    return {
        "verdict_core_cc": verdict_core_cc,
        "resolution_status": status,
        "bound_profile_commitment": bound_profile_commitment,
    }

KEYS = ("verdict_core_cc", "resolution_status", "bound_profile_commitment")

def run(path):
    doc = json.load(open(path))
    fails = 0
    for v in doc["vectors"]:
        got, exp = verdict_binding(v), v["expect"]
        ok = all(got[k] == exp[k] for k in KEYS)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {v['name']:<34} status={got['resolution_status']:<10} "
              f"verdict_core_cc={got['verdict_core_cc'][:12]}")
    print(f"{len(doc['vectors']) - fails}/{len(doc['vectors'])} vectors reproduced")
    return fails

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    sys.exit(1 if run(arg or os.path.join(here, "verdict-profile-binding-v0.vectors.json")) else 0)
