#!/usr/bin/env python3
"""captured-admission.v0 — the shared lifecycle primitive under review verdicts, contribution
settlement, and TEE attestation epochs: "captured admission with bounded authority or obligation".

Greenlit 2026-08-02 with pipavlo82 (Pavlo) + babyblueviper1 (Fede) + Jimmy Shi. Three domain lifecycles
(review dispositions, settlement milestones, enclave key-epochs) share ONE structural spine; this file
pins the shared CORE — capture->admission binding, admission kind, enumerable index/epoch, temporal bound,
append-only transitions, anchor-time resolution, non-retroactivity, derived absence/conflict — as
recomputable vectors. Domain PROFILES own their own terminal vocabularies on top; this file is
profile-agnostic core only (a profile is passed in per case as its permitted-disposition set).

Pavlo's guard, encoded literally: a record keeps TWO stored dimensions in SEPARATE namespaces --
  lifecycle_state  (authority: active / expired / revoked / superseded)  -- a timing/authority condition
  disposition      (a profile's permitted completion over an admitted obligation) -- a validity judgment
-- and absence + conflict are DERIVED predicates recomputed from the enumerable sequence, never stored.
That separation is the whole point: a timing or authority condition must never collapse into a validity
judgment. `missing` is therefore not a state anyone writes -- it is recomputed as
(admitted AND window elapsed AND no valid completing disposition).

Modes:
  obligation   -- resolve one admitted obligation index at eval_at:
                  resolved:<disp> | pending | liveness_failure | conflict | invalid_admission
  authority    -- attribute one claim against the epoch in force at the CLAIM'S OWN anchor time:
                  attributed | out_of_authority | invalid_admission   (later expiry/revoke acts forward only)
  disposition  -- one disposition's own validity, class PRESERVED (never relabeled to a neighbour):
                  disposition:<kind> | rejected:<kind>
"""
import json, sys


def _binding_ok(case):
    # (core-1) exact capture->admission binding: the admitted object hash equals the captured object hash.
    return case["admission"]["captured_object_hash"] == case["capture"]["object_hash"]


# -- mode=obligation -----------------------------------------------------------------------------------
def obligation(case):
    if not _binding_ok(case):
        return "invalid_admission", ["capture_admission_hash_mismatch"]
    adm = case["admission"]; idx = adm["admission_index"]; deadline = adm["response_deadline"]
    permitted = set(adm["profile"]["permitted_dispositions"]); eval_at = case["eval_at"]
    # a disposition COMPLETES iff valid: references THIS index, kind permitted, at>=admitted, own predicate holds
    valid = []
    for d in case.get("dispositions", []):
        if d["references_index"] != idx:
            continue
        if d["kind"] in permitted and d["at"] >= adm["admitted_at"] and d.get("binds", True):
            valid.append(d)
    n = len(valid)
    if n >= 2:                                            # (core-8) DERIVED conflict, never silent overwrite
        return "conflict", [f"valid_completing_dispositions={n}", "no_silent_overwrite"]
    if n == 1:                                            # semantic disposition dimension
        return f"resolved:{valid[0]['kind']}", [f"disposition={valid[0]['kind']}", "obligation_satisfied"]
    # n == 0 -- keep the timing condition strictly separate from any validity judgment
    if eval_at >= deadline:                               # (core-8) DERIVED absence = liveness, NEVER 'rejected'
        return "liveness_failure", [f"eval_at={eval_at}>=deadline={deadline}",
                                    "no_valid_completing_disposition", "timing_not_validity"]
    return "pending", [f"eval_at={eval_at}<deadline={deadline}", "within_window"]


# -- mode=authority ------------------------------------------------------------------------------------
def authority(case):
    if not _binding_ok(case):
        return "invalid_admission", ["capture_admission_hash_mismatch"]
    adm = case["admission"]; epoch = adm["epoch_id"]; activated = adm["activated_at"]
    # the authority window ends at the EARLIEST of expiry / revoke / supersede (a lifecycle transition)
    ends = []
    if adm.get("expiry") is not None:
        ends.append(("expired", adm["expiry"]))
    for t in case.get("transitions", []):
        if t["references_epoch"] == epoch and t["kind"] in ("revoked", "superseded"):
            ends.append((t["kind"], t["at"]))
    end_kind, end_at = min(ends, key=lambda e: e[1]) if ends else (None, None)
    # (core-9) lifecycle_state is a SEPARATE dimension -- reported, but NOT used to judge a prior claim
    life = "active" if end_at is None or case["eval_at"] < end_at else end_kind
    c = case["claim"]
    if c["references_epoch"] != epoch:
        return "out_of_authority", [f"lifecycle_state_now={life}", "claim_references_other_epoch"]
    # (core-6)(core-7) resolve against the epoch in force at the CLAIM'S OWN anchor time -- forward-only
    in_window = c["anchor_time"] >= activated and (end_at is None or c["anchor_time"] < end_at)
    if in_window:
        return "attributed", [f"lifecycle_state_now={life}", f"claim_anchor={c['anchor_time']}",
                              "in_force_at_claim_anchor_time", "not_retroactively_invalidated"]
    return "out_of_authority", [f"lifecycle_state_now={life}", f"claim_anchor={c['anchor_time']}",
                                f"authority_window=[{activated},{end_at})"]


# -- mode=disposition ----------------------------------------------------------------------------------
# One disposition's own validity, in its DECLARED class. A predicate miss rejects AS THAT KIND -- never
# relabeled to a neighbouring kind (that cross-class relabel is the failure this guards).
def disposition(case):
    d = case["disposition"]; permitted = set(case["profile"]["permitted_dispositions"]); k = d["kind"]
    reasons = []
    if k not in permitted:
        reasons.append("kind_not_permitted")
    if not d.get("references_ok", True):
        reasons.append("does_not_reference_its_admission")
    if not d.get("binds", True):
        reasons.append("binding_predicate_failed")
    if reasons:
        return f"rejected:{k}", reasons + ["class_preserved_not_relabeled"]
    return f"disposition:{k}", ["valid_in_declared_class"]


def check(case):
    m = case.get("mode")
    v, notes = {"obligation": obligation, "authority": authority, "disposition": disposition}[m](case)
    return v == case["expected_verdict"], v, notes


if __name__ == "__main__":
    fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "vectors.json"))
    fails = 0
    for c in fx["cases"]:
        ok, v, notes = check(c)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<48} -> {v:<28} (want {c['expected_verdict']})  · {' · '.join(notes)}")
    print(f"\n{len(fx['cases']) - fails}/{len(fx['cases'])} cases reproduced" + ("" if not fails else "  <- MISMATCH"))
    sys.exit(1 if fails else 0)
