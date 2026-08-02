#!/usr/bin/env python3
"""captured-admission.v0 — the shared lifecycle primitive under review verdicts, contribution
settlement, and TEE attestation epochs: "captured admission with bounded authority or obligation".

Greenlit 2026-08-02 with pipavlo82 (Pavlo), babyblueviper1 (Fede), Jimmy Shi; then shaped by Pavlo's
blind-diff on PR #5 (the five control families + the core-vs-profile split pinned below).

Pavlo's guard, encoded literally: a record keeps TWO stored dimensions in SEPARATE namespaces --
  lifecycle_state  (authority: active / expired / revoked / superseded)  -- a timing/authority condition
  disposition      (a profile's permitted completion over an admitted obligation) -- a validity judgment
-- and absence + conflict are DERIVED predicates recomputed from the enumerable sequence, never stored.
`missing` is not a state anyone writes; it is recomputed. Semantic resolution and liveness are two separate
recomputable facts: a LATE disposition resolves without erasing the missed deadline.

as_of is a REQUIRED first-class input: every verdict is a pure function of (record, as_of), and the
evaluator IGNORES every event whose own commit/anchor time is later than as_of -- a future record never
affects an earlier snapshot (disposition.at <= as_of; claim.anchor_time; transition.at <= as_of).

CORE proves identity, timing, commitment, exact binding, ordering, continuity. PROFILE/POLICY owns the
vocabularies, which capturer roles are incentive-aligned, and which external anchor classes count as
independent -- those resolve from profile-pinned evidence (capture_policy_id), never issuer declarations.

Modes:
  obligation   -- resolve one admitted index at as_of (semantic AND liveness, never collapsed)
  authority    -- attribute one claim against the epoch in force at the CLAIM'S OWN anchor time
  disposition  -- one disposition's validity in its declared class (unrecognized kind != rejected:<echo>)
  enumerate    -- sequence-level completeness/continuity of the admitted/published set
  capture      -- capture-evidence provenance + exact binding into admission
"""
import hashlib, json, sys

RECOGNIZED_TRANSITIONS = {"revoked", "superseded", "reactivated"}
TERMINAL_TRANSITIONS = {"revoked", "superseded"}


def _h(s): return hashlib.sha256(s.encode()).hexdigest()[:16]
def _sig(idty, obj, at): return "sig:" + _h(f"{idty}|{obj}|{at}")
def _capcommit(c):  # binds the COMPLETE declared capture record (every field except the commitment itself)
    fields = ["capture_id", "captured_object_hash", "capturer_identity", "captured_at", "signature",
              "anchor_ref", "anchor_class", "anchor_time", "capture_policy_id"]
    return "cm:" + _h("|".join(str(c[k]) for k in fields))
def _chain_head(seq_id, entries):
    prev = "GEN:" + str(seq_id)
    for e in entries:
        prev = _h(f"{e['index']}|{e['commitment']}|{prev}")
    return "head:" + prev
def _binding_ok(case):
    return case["admission"]["captured_object_hash"] == case["capture"]["object_hash"]
def _asof(case):
    return case.get("as_of")  # as_of is REQUIRED (obligation/authority); no silent eval_at fallback


# -- mode=obligation -----------------------------------------------------------------------------------
def obligation(case):
    if not _binding_ok(case):
        return "invalid_admission", ["capture_admission_hash_mismatch"]
    as_of = _asof(case)
    if as_of is None:
        return "as_of_required", ["as_of_is_a_required_first_class_input"]
    adm = case["admission"]
    if as_of < adm["admitted_at"]:                    # snapshot predates the admission -> not visible yet
        return "admission_not_yet_visible", [f"as_of={as_of}<admitted_at={adm['admitted_at']}",
                                             "future_record_ignored_on_earlier_snapshot"]
    if adm.get("outcome", "accepted") == "rejected_at_admission":
        return "not_admitted:rejected_at_admission", ["admission_rejected", "no_obligation_created",
                                                      "references_request_capture_only"]
    idx = adm["admission_index"]; deadline = adm["response_deadline"]
    permitted = set(adm["profile"]["permitted_dispositions"])
    # a disposition COMPLETES iff valid AND visible at as_of (future events ignored on an earlier snapshot)
    valid = [d for d in case.get("dispositions", [])
             if d["references_index"] == idx and d["kind"] in permitted
             and d["at"] >= adm["admitted_at"] and d["at"] <= as_of and d.get("binds", True)]
    if len(valid) >= 2:
        return "conflict", [f"valid_completing_dispositions={len(valid)}", "no_silent_overwrite"]
    if len(valid) == 1:
        d = valid[0]; met = d["at"] <= deadline
        return (f"resolved:{d['kind']}|{'met' if met else 'late'}",
                [f"disposition={d['kind']}",
                 "deadline_met" if met else "deadline_breached_late_resolution_not_erased",
                 "semantic_and_liveness_separate"])
    if as_of >= deadline:
        return "unresolved|liveness_failure", [f"as_of={as_of}>=deadline={deadline}",
                                               "no_valid_disposition_by_deadline", "timing_not_validity"]
    return "pending|open", [f"as_of={as_of}<deadline={deadline}", "within_window"]


# -- mode=authority ------------------------------------------------------------------------------------
def authority(case):
    if not _binding_ok(case):
        return "invalid_admission", ["capture_admission_hash_mismatch"]
    adm = case["admission"]; epoch = adm["epoch_id"]; activated = adm["activated_at"]; as_of = _asof(case)
    if as_of is None:
        return "as_of_required", ["as_of_is_a_required_first_class_input"]
    if adm.get("expiry") is not None and adm["expiry"] <= activated:
        return "invalid_admission", ["expiry_at_or_before_activation"]
    if as_of < activated:                             # snapshot predates the epoch -> not active yet
        return "epoch_not_yet_active", [f"as_of={as_of}<activated_at={activated}",
                                        "future_record_ignored_on_earlier_snapshot"]
    # VISIBILITY FIRST: a transition after as_of must never affect this snapshot (Pavlo). All validation,
    # conflict resolution, and boundary selection run ONLY over the visible set.
    et = [t for t in case.get("transitions", [])
          if t["references_epoch"] == epoch and t["at"] <= as_of]
    for t in et:
        if t["kind"] not in RECOGNIZED_TRANSITIONS:
            return "invalid_transition", [f"unrecognized_transition_kind={t['kind']}"]
    if any(t["kind"] in TERMINAL_TRANSITIONS and t["at"] < activated for t in et):
        return "invalid_transition", ["terminal_transition_before_activation", "append_only_violation"]
    # profile-owned: a supersede must name a bound successor epoch when the policy requires it
    if case.get("profile", {}).get("requires_supersede_successor") and \
            any(t["kind"] == "superseded" and not t.get("successor_epoch") for t in et):
        return "invalid_transition", ["supersede_without_bound_successor"]
    terms = [t for t in et if t["kind"] in TERMINAL_TRANSITIONS]
    reacts = [t for t in et if t["kind"] == "reactivated"]
    if terms and any(r["at"] > min(t["at"] for t in terms) for r in reacts):
        return "rollback_conflict", ["reactivation_after_terminal", "no_rollback_to_active"]
    if len({(t["kind"], t["at"]) for t in terms}) >= 2:
        return "transition_conflict", [f"distinct_terminal_transitions={len({(t['kind'], t['at']) for t in terms})}",
                                       "ambiguous_authority_end"]
    # effective boundary from expiry (always in force) + VISIBLE terminal only (future terminal ignored)
    ends = []
    if adm.get("expiry") is not None:
        ends.append(("expired", adm["expiry"]))
    ends += [(t["kind"], t["at"]) for t in terms if t["at"] <= as_of]
    end_kind, end_at = min(ends, key=lambda e: e[1]) if ends else (None, None)
    life = "active" if end_at is None or as_of < end_at else end_kind
    c = case["claim"]
    if c["anchor_time"] > as_of:                              # a future claim is invisible on an earlier snapshot
        return "claim_not_yet_visible", [f"claim_anchor={c['anchor_time']}>as_of={as_of}",
                                         "future_record_ignored_on_earlier_snapshot"]
    if c["references_epoch"] != epoch:
        return "out_of_authority", [f"lifecycle_state_now={life}", "claim_references_other_epoch"]
    in_window = c["anchor_time"] >= activated and (end_at is None or c["anchor_time"] < end_at)
    if in_window:
        return "attributed", [f"lifecycle_state_now={life}", f"claim_anchor={c['anchor_time']}",
                              "in_force_at_claim_anchor_time", "not_retroactively_invalidated"]
    return "out_of_authority", [f"lifecycle_state_now={life}", f"claim_anchor={c['anchor_time']}",
                                f"authority_window=[{activated},{end_at})"]


# -- mode=disposition ----------------------------------------------------------------------------------
# Class preservation applies ONLY AFTER structural admission into a KNOWN declared class. A kind outside
# the profile's declared vocabulary is `unrecognized_disposition_kind` -- NOT rejected:<input-string>,
# which would let arbitrary input extend the canonical output vocabulary.
def disposition(case):
    d = case["disposition"]; permitted = set(case["profile"]["permitted_dispositions"]); k = d["kind"]
    if k not in permitted:
        return "unrecognized_disposition_kind", ["kind_not_in_profile_vocabulary", "no_input_controlled_output"]
    reasons = []
    if not d.get("references_ok", True):
        reasons.append("does_not_reference_its_admission")
    if not d.get("binds", True):
        reasons.append("binding_predicate_failed")
    if reasons:
        return f"rejected:{k}", reasons + ["class_preserved_not_relabeled"]
    return f"disposition:{k}", ["valid_in_declared_class"]


# -- mode=enumerate ------------------------------------------------------------------------------------
# Completeness + continuity of the admitted/published set from an independently anchored ordered sequence.
# Scope: this proves the set is complete and continuous -- NOT that every eligible object was admitted
# (that is the separate capture/non-suppression predicate). A Merkle root alone is not enumerable; here the
# authenticated structure is an append-only hash chain with an independently anchored HEAD.
def enumerate_seq(case):
    s = case["sequence"]; first = s["first_index"]; mx = s["max_committed_index"]; entries = s["entries"]
    if mx < first or not entries:
        return "invalid_sequence", [f"first={first}", f"max={mx}", f"n={len(entries)}"]
    given = [e["index"] for e in entries]
    if given != sorted(given):
        return "out_of_order", [f"given_order={given}"]
    seen = {}
    for e in entries:
        i = e["index"]
        if i in seen:
            if seen[i] != e["commitment"]:
                return f"conflicting_index:{i}", ["two_commitments_same_index"]
            return f"duplicate:{i}", ["same_index_same_commitment_repeated"]
        seen[i] = e["commitment"]
    for i in range(first, mx + 1):
        if i not in seen:
            return f"gap:{i}", [f"missing_index_in_[{first},{mx}]"]
    uniq = [e for e in entries]
    if _chain_head(s["sequence_id"], uniq) != s["anchored_head"]:
        return "commitment_mismatch", ["recomputed_head_ne_anchored_head"]
    return "complete", [f"contiguous_[{first},{mx}]", "chain_head_matches_anchor"]


# -- mode=capture --------------------------------------------------------------------------------------
# CORE proves: exact binding, signature, anchor-opens-to-record, timing. POLICY (profile-pinned) proves:
# capturer role is the expected incentive-aligned party, and the anchor class is acceptably independent.
# "independent" is never a self-declared boolean.
def capture(case):
    cap = case["capture"]; adm = case["admission"]; pol = case["profile"]
    if adm["capture_id"] != cap["capture_id"] or adm["captured_object_hash"] != cap["captured_object_hash"]:
        return "capture_binding_mismatch", ["admission_does_not_bind_this_capture"]
    if cap["signature"] != _sig(cap["capturer_identity"], cap["captured_object_hash"], cap["captured_at"]):
        return "invalid_capture_signature", ["signature_does_not_verify_for_capturer_identity"]
    if cap["anchor_commitment"] != _capcommit(cap):
        return "anchor_does_not_open", ["anchor_commitment_does_not_open_to_complete_capture_record"]
    if cap["captured_at"] > cap["anchor_time"]:        # enforce captured_at <= anchor_time <= accepted_at
        return "invalid_capture_timing", [f"captured_at={cap['captured_at']}>anchor_time={cap['anchor_time']}"]
    if cap["anchor_time"] > adm["accepted_at"]:
        return "capture_anchored_after_admission", [f"anchor_time={cap['anchor_time']}>accepted_at={adm['accepted_at']}"]
    if cap["capturer_identity"] == pol.get("processor_identity") and pol.get("requires_requester_capture"):
        return "processor_signed_capture", ["profile_requires_requester_or_contributor_capture"]
    if cap["capturer_identity"] not in pol["acceptable_capturer_identities"]:
        return "capturer_not_incentive_aligned", ["identity_not_an_acceptable_capturer_role"]
    if cap["anchor_class"] not in pol["acceptable_anchor_classes"]:
        return "unsupported_anchor_class", [f"anchor_class={cap['anchor_class']}_not_in_policy"]
    return "capture_admitted", ["binding+signature+anchor_open+timing (core)", "role+anchor_class (policy)"]


# -- mode=idempotency ----------------------------------------------------------------------------------
# Idempotency is keyed by the capture, but admission_index must NOT be content-derived -- that would
# conflate request identity with the monotonic enumerable position (Pavlo). Two separate identities:
#   admission_id    = H(profile_id || canonical_capture_ref)   -- deterministic REQUEST identity
#   admission_index = a sequence position assigned once on first acceptance  -- monotonic ORDER identity
# with an immutable admission_id -> admission_index mapping. A retry carrying the same exact canonical
# capture returns the existing receipt+index (no-op); it never mints a second admission.
def idempotency(case):
    pid = case["profile_id"]; recs = case["records"]
    for r in recs:  # admission_id must be DERIVED, not an arbitrary requester label
        if r["admission_id"] != "aid:" + _h(f"{pid}|{r['canonical_capture_ref']}"):
            return "admission_id_not_derived", [f"capture_id={r['capture_id']}",
                                                "admission_id != H(profile_id||canonical_capture_ref)"]
    cap_to_ref = {}  # a capture_id opening to two different canonical contents is a conflict
    for r in recs:
        cid = r["capture_id"]
        if cid in cap_to_ref and cap_to_ref[cid] != r["canonical_capture_ref"]:
            return f"capture_id_conflict:{cid}", ["same_capture_id_different_canonical_content"]
        cap_to_ref[cid] = r["canonical_capture_ref"]
    aid_to_idx = {}  # the admission_id -> admission_index mapping must be immutable
    for r in recs:
        aid = r["admission_id"]
        if aid in aid_to_idx and aid_to_idx[aid] != r["admission_index"]:
            return f"idempotency_violation:{aid}", ["same_admission_id_two_indices"]
        aid_to_idx[aid] = r["admission_index"]
    if len(recs) > len({r["admission_id"] for r in recs}):
        return "idempotent_replay", ["retry_returns_existing_receipt_and_index", "no_second_admission"]
    return "admitted_ok", ["one_receipt_one_index_per_request_identity"]


def check(case):
    m = case.get("mode")
    fn = {"obligation": obligation, "authority": authority, "disposition": disposition,
          "enumerate": enumerate_seq, "capture": capture, "idempotency": idempotency}[m]
    v, notes = fn(case)
    return v == case["expected_verdict"], v, notes


if __name__ == "__main__":
    fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "vectors.json"))
    fails = 0
    for c in fx["cases"]:
        ok, v, notes = check(c)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<50} -> {v:<30} (want {c['expected_verdict']})  · {' · '.join(notes)}")
    print(f"\n{len(fx['cases']) - fails}/{len(fx['cases'])} cases reproduced" + ("" if not fails else "  <- MISMATCH"))
    sys.exit(1 if fails else 0)
