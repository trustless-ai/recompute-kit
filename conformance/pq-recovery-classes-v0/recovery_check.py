#!/usr/bin/env python3
"""pq-recovery-classes.v0 — recomputable authority-transition classes for per-agent PQ keys.

A key-binding scheme survives past a single incident only if a third party can INDEPENDENTLY tell what
kind of authority transition happened — routine rotation, full-agent kill, or a fleet-wide seed-recovery —
from the anchored trail alone, not from the operator's stated intent. So each class is a FALSIFIABLE claim
with its own predicate; a record is judged ONLY against its declared class and, if the predicate fails, is
`rejected` — never silently relabeled as an adjacent class (cross-class confusion is the failure this guards).

Classes (design 2026-07-31, with babyblueviper1 + pipavlo82):
  rotation           continuity  — names a successor binding that exists, is in force from >= this anchor
                                    time, and is not itself revoked. (per-agent, SIWE owner-authorized)
  agent_terminal     termination — asserts NO successor: no key can resolve in force for any t after this
                                    anchor time. (per-agent, SIWE owner-authorized)
  seed_epoch_rotation systemic   — every new per-agent key equals derive(S', registry, agent_id), AND the
                                    statement is anchored under an identity that provably does NOT derive
                                    from any seed (the classical deployer key, control proven by the anchor
                                    tx sender, not a separable signature). This domain separation is IN the
                                    predicate: without it the most powerful class would inherit the weakest
                                    (per-agent) authorization — a single compromised agent key reaching fleet
                                    scope. (fleet, deployer-authorized)

Authority-over-a-compromised-root cannot reduce to the thing being replaced (same shape as anchor-time over
signature-time): a seed rotation authorized under the seed it replaces is forgeable, so authority rests on
the deployer key whose possession is proven by its own record() transaction. What authorizes replacing the
DEPLOYER key is deliberately OUT OF SCOPE (see README) — stated, not left silent.
"""
import hashlib, json, sys

DEPLOYER = "0xff9a176577fb42b6bc9c19fd05a241e8fcd0ca14"  # classical anchor identity; not a seed-derived key

# Test key-derivation stand-in (the vector pins the PREDICATE, not the live master seed): a seed-derived
# per-agent pubkey is a deterministic function of (seed_epoch, registry, agent_id). Real deployment uses
# ml_dsa65.keygen(sha256(MASTER_SEED:...:seed_epoch)); here the shape is what matters for the blind diff.
def derive(seed_epoch, registry, agent_id):
    return "kd:" + hashlib.sha256(f"SEED{seed_epoch}:{registry.lower()}:{agent_id}".encode()).hexdigest()

# resolveInForce, byte-for-byte with the gateway/enforcer: a binding governs from its anchor time; a
# revoked_at ends its authority (artifacts at/after it are no longer governed).
def in_force(bindings, at):
    elig = [b for b in bindings if b["binding_anchor_time"] <= at and not (b.get("revoked_at") is not None and at >= b["revoked_at"])]
    if not elig:
        return None
    return max(elig, key=lambda b: b["binding_anchor_time"])

def has_any_in_force_after(bindings, t0):
    # is there ANY time t > t0 at which some binding is in force? (kill must make this false)
    for b in bindings:
        rev = b.get("revoked_at")
        # a binding still confers authority after t0 iff it isn't revoked at/before t0
        if rev is None or rev > t0:
            return True
    return False

def check(case):
    s = case["statement"]; cls = s["class"]; hist = case.get("history_after", [])
    auth = s.get("auth", {}); at = s["anchor_time"]; notes = []

    if cls == "rotation":
        owner_ok = auth.get("path") == "siwe_owner" and auth.get("identity", "").lower() == s.get("owner", "").lower()
        succ = next((b for b in hist if b["content_address"] == s.get("superseded_by_content_address")), None)
        succ_ok = bool(succ) and succ["binding_anchor_time"] >= at and succ.get("revoked_at") is None
        notes.append(f"owner_authorized={owner_ok}"); notes.append(f"successor_exists_in_force_unrevoked={succ_ok}")
        verdict = "continuity" if (owner_ok and succ_ok) else "rejected"

    elif cls == "agent_terminal":
        owner_ok = auth.get("path") == "siwe_owner" and auth.get("identity", "").lower() == s.get("owner", "").lower()
        terminated = not has_any_in_force_after(hist, at)
        notes.append(f"owner_authorized={owner_ok}"); notes.append(f"no_in_force_key_after={terminated}")
        verdict = "terminated" if (owner_ok and terminated) else "rejected"

    elif cls == "seed_epoch_rotation":
        # domain separation is IN the predicate: fleet scope demands a non-seed-derived, tx-proven identity.
        dep_ok = (auth.get("path") == "deployer_tx"
                  and auth.get("identity", "").lower() == DEPLOYER
                  and auth.get("anchor_tx_from", "").lower() == auth.get("identity", "").lower())
        keys_ok = all(k["pq_pubkey"] == derive(s["seed_epoch"], k["registry"], k["agent_id"]) for k in s.get("new_keys", [])) and len(s.get("new_keys", [])) > 0
        notes.append(f"deployer_tx_authority={dep_ok}"); notes.append(f"all_new_keys_derive_from_S'={keys_ok}")
        verdict = "systemic_recovery" if (dep_ok and keys_ok) else "rejected"

    else:
        verdict = "rejected"; notes.append(f"unknown_class={cls}")

    ok = verdict == case["expected_verdict"]
    return ok, verdict, notes

if __name__ == "__main__":
    fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "vectors.json"))
    fails = 0
    for c in fx["cases"]:
        ok, verdict, notes = check(c)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<40} → {verdict:<17} (want {c['expected_verdict']})  · {' · '.join(notes)}")
    print(f"\n{len(fx['cases'])-fails}/{len(fx['cases'])} cases reproduced" + ("" if not fails else "  ← MISMATCH"))
    sys.exit(1 if fails else 0)
