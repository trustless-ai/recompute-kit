#!/usr/bin/env python3
"""profile-commitment-loop.v0 — recompute the WHOLE loop end to end, chaining the two sub-gates over the
SAME task+escrow so the seam between them is a mechanical check, not a shared constant.

profile-amendment-v0 decides which profile is effective (amendment end). verdict-profile-binding-v0 decides
whether a resolver's verdict commits to a given effective profile (resolution end). Each correctly tests its
own predicate in isolation, and both vector sets happen to reference the same profile commitment — but that
equality lives in prose, not in a gate. A shared constant maintained by hand is exactly the side-channel
reference the whole family exists to kill, one level up in our own fixtures: change the profile in one suite
and not the other and both stay green while the loop is silently broken (WG question, @babyblueviper1 on #41).

This gate closes that: it runs the REAL amendment gate to compute effective_profile_commitment, then feeds
THAT value (not a hand-set constant) as the resolution gate's task_effective_profile_commitment. So the
resolution gate's own profile-match predicate becomes the seam check. The loop is `closed` iff the amendment
is a permitted transition AND the verdict is bound to the amendment's computed effective profile; otherwise
`open`, fail closed. Together: task.profile_commitment == verdict.profile_commitment, both ends cryptographic
and now mechanically chained rather than asserted (Pavlo Tvardovskyi's invariant; @Pavlentyy82).

Composition, not reimplementation: it imports the two shipped gates and calls their pure functions, so this
suite cannot drift from what #40 and #41 actually enforce.
"""
import sys, json, os, importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))

def _load(mod_name, rel):
    path = os.path.join(_HERE, "..", rel)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

# reuse the ACTUAL shipped gates (#40, #41) — never a local copy
_amend = _load("amendment_gate", "profile-amendment-v0/amendment_gate.py")
_verdict = _load("verdict_binding_gate", "verdict-profile-binding-v0/verdict_binding_gate.py")

def loop(v):
    # amendment end: run the real gate over the amendment-side inputs
    transition = _amend.profile_transition({
        "in_force_profile": v["in_force_profile"],
        "proposed_profile": v["proposed_profile"],
        "escrow_ref": v["escrow_ref"],
        "amendment": v.get("amendment"),
        "authorizations": v.get("authorizations") or {},
        "required_parties": v.get("required_parties") or ["buyer", "supplier"],
    })
    # resolution end: feed the amendment's COMPUTED effective as task_effective — this is the seam.
    binding = _verdict.verdict_binding({
        "verdict_core": v["verdict_core"],
        "task_effective_profile_commitment": transition["effective_profile_commitment"],
        "resolver_sig": v.get("resolver_sig"),
    })
    # Note (babyblueviper1, #42): because a non-permitted amendment alone forces closed=False, the
    # amendment side can mask a resolution-side fault. So open-verdict-wrong-profile (amendment permitted)
    # is the vector whose loop_status isolates the seam; open-bare-swap's refusal masks the same drift.
    closed = (transition["transition_status"] == "permitted"
              and binding["resolution_status"] == "bound")
    return {
        "transition_status": transition["transition_status"],
        "resolution_status": binding["resolution_status"],
        "effective_profile_commitment": transition["effective_profile_commitment"],
        "bound_profile_commitment": binding["bound_profile_commitment"],
        "loop_status": "closed" if closed else "open",
    }

KEYS = ("transition_status", "resolution_status", "effective_profile_commitment",
        "bound_profile_commitment", "loop_status")

def run(path):
    doc = json.load(open(path))
    fails = 0
    for v in doc["vectors"]:
        got, exp = loop(v), v["expect"]
        ok = all(got[k] == exp[k] for k in KEYS)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {v['name']:<34} loop={got['loop_status']:<7} "
              f"transition={got['transition_status']:<10} resolution={got['resolution_status']}")
    print(f"{len(doc['vectors']) - fails}/{len(doc['vectors'])} vectors reproduced")
    return fails

if __name__ == "__main__":
    arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    sys.exit(1 if run(arg or os.path.join(_HERE, "profile-commitment-loop-v0.vectors.json")) else 0)
