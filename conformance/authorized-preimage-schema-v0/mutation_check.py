#!/usr/bin/env python3
"""One-site oracle mutations: each named verifier bug must change ITS INTENDED DIMENSION on its named
witness case while the controls stay exactly as expected on every dimension.

Kill criterion (revised after review on #48): a mutant is killed only when the dimension it targets changes on the
witness case, judged against the FULL expected result. An earlier revision judged every mutant on the single scalar
required_verification_outcome, which is exactly the collapse this profile exists to replace: a mutant that corrupts
which dimension reported what survived whenever accept/reject happened to be preserved. All dimensions that changed
are recorded, so a mutant that kills for a different reason than intended is visible, not silently counted."""

import json
from pathlib import Path
import sys

import schema_check as baseline

HERE = Path(__file__).resolve().parent
CONTROLS = ["A1_CONTROL_CURRENT_AUTHORIZED", "N8_DECISION_REF_TAMPERED"]
ANY_STATE = "any(set(names) == set(state) for state in states)"
MUTANTS = [
    ("M1_DECLARED_SET_TRUSTED_DIRECTLY", "N1_SELF_CONSISTENT_REDUCED_PREIMAGE", ANY_STATE, "True", "preimage_schema_status"),
    ("M2_RECOMPUTE_FAILURE_BYPASSES_AUTHORIZATION", "N7_RECOMPUTE_FAILURE_MUST_NOT_BYPASS_AUTHORIZATION",
     'if signature == "satisfied" and issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     'if recompute == "cannot_establish" and signature == "satisfied" or (signature == "satisfied" and issuer == "satisfied" and '
     'proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied"):  # M2/M8/M14/M22', "required_verification_outcome"),
    ("M3_DUPLICATE_NAMES_SILENTLY_DEDUPED", "N4_DUPLICATE_NAME_MALFORMED",
     "if len(set(declared)) != len(declared):  # M3", "if False:  # M3", "preimage_schema_status"),
    ("M4_NON_STRING_ENTRIES_COERCED_AWAY", "N5_NON_STRING_ENTRY_MALFORMED",
     "if not (isinstance(declared, list) and all(type(f) is str for f in declared)):  # M4",
     "if isinstance(declared, list):\n        declared = [f for f in declared if type(f) is str]\n"
     "    if not isinstance(declared, list):  # M4", "preimage_schema_status"),
    ("M5_UNKNOWN_POLICY_VERSION_ACCEPTED", "N3_UNREGISTERED_POLICY_VERSION",
     "if states is None:  # M5",
     'if states is None:\n        return "satisfied", "DECLARED_SET_REGISTERED"\n    if False:  # M5', "preimage_schema_status"),
    ("M6_PROPER_SUBSET_ACCEPTED", "N1_SELF_CONSISTENT_REDUCED_PREIMAGE",
     ANY_STATE, "any(set(names) <= set(state) for state in states)", "preimage_schema_status"),
    ("M7_SUPERSET_ACCEPTED", "N2_SUPERSET_WITH_UNREGISTERED_FIELD",
     ANY_STATE, "any(set(names) >= set(state) for state in states)", "preimage_schema_status"),
    ("M8_SIGNATURE_NOT_CHECKED", "N9_SIGNATURE_INVALID_ISOLATED",
     'if signature == "satisfied" and issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     'if issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22', "required_verification_outcome"),
    ("M9_LIST_ORDER_TREATED_AS_IDENTITY", "A2_REORDERED_DECLARED_LIST_SAME_SET",
     ANY_STATE, "any(list(names) == list(state) for state in states)", "preimage_schema_status"),
    ("M10_ANY_VERSIONS_REGISTRY_ACCEPTED", "N10_CURRENT_SET_UNDER_OLD_VERSION",
     ANY_STATE, 'any(set(names) == set(state) for group in registry["states"].values() for state in group)', "preimage_schema_status"),
    ("M11_ONE_VERSION_ONE_SCHEMA_ASSUMED", "A4_V18_REGISTERED_STATE_2",
     ANY_STATE, "set(names) == set(states[0])", "preimage_schema_status"),
    # Reported on #48 (independent reviewer): recompute over the REGISTERED set instead of the DECLARED one. Every
    # authorized case is unchanged and every unauthorized case is rejected either way, so on the scalar outcome axis
    # this survived; it destroys exactly the "clean recompute over an unauthorized set" distinction N1 exists to draw.
    ("M12_RECOMPUTE_OVER_REGISTERED_SET_NOT_DECLARED", "N1_SELF_CONSISTENT_REDUCED_PREIMAGE",
     "    preimage = {name: content.get(name) for name in names}\n",
     "    _states = _REGISTRY[\"states\"].get(content.get(\"policy_version\")) or [names]\n"
     "    _pick = next((s for s in _states if set(s) == set(names)), _states[0])\n"
     "    preimage = {name: content.get(name) for name in sorted(_pick)}\n",
     "decision_ref_recompute_status"),
    # Completeness is a constant dimension. A constant is emitted correctly by an implementation that computes
    # nothing, so it needs a mutant that claims it (must be killed) and the converse: promoting the non-claim
    # into a failure (must also be killed). Controls exclude the intended dimension by design.
    ("M13_COMPLETENESS_CLAIMED_SATISFIED", "A1_CONTROL_CURRENT_AUTHORIZED",
     'COMPLETENESS_STATUS = "cannot_establish"', 'COMPLETENESS_STATUS = "satisfied"',
     "registered_set_completeness_status"),
    ("M14_COMPLETENESS_NON_CLAIM_PROMOTED_TO_FAILURE", "A4_V18_REGISTERED_STATE_2",
     'if signature == "satisfied" and issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     'if signature == "satisfied" and issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied" and '
     'COMPLETENESS_STATUS == "satisfied":  # M2/M8/M14/M22',
     "required_verification_outcome", ["N8_DECISION_REF_TAMPERED", "N9_SIGNATURE_INVALID_ISOLATED"]),
    # Reported on #48 (independent reviewer, 2026-09-21). M15: parse the signed content last-wins instead of failing
    # closed on a repeated member name. M16: ignore the proof's canonicalization_version. M17: treat a lone UTF-16
    # surrogate string as a supported preimage value (it then cannot be encoded; the verifier's generic error path
    # collapses every dimension to cannot_establish, which is why the visible change lands on the schema dimension).
    ("M15_DUPLICATE_MEMBERS_PARSED_LAST_WINS", "N11_DUPLICATE_CONTENT_MEMBER_MALFORMED",
     'content = json.loads(data["event"]["content"], object_pairs_hook=no_duplicate_members)  # M15',
     'content = json.loads(data["event"]["content"])  # M15', "preimage_schema_status"),
    ("M16_CANONICALIZATION_VERSION_IGNORED", "N12_UNSUPPORTED_CANONICALIZATION_VERSION",
     'if "canonicalization_version" in names and content.get("canonicalization_version") != SUPPORTED_CANONICALIZATION:  # M16',
     "if False:  # M16", "decision_ref_recompute_status"),
    ("M17_LONE_SURROGATE_TREATED_AS_SUPPORTED", "N13_LONE_SURROGATE_PREIMAGE_VALUE",
     "return _encodable(value)  # M17", "return True  # M17", "preimage_schema_status"),
    # M18 (2026-09-21, on the profile's normative scope): a stdlib checker that admits floats. json.dumps(0.5) happens
    # to equal the RFC 8785 form, so N14's decision_ref recomputes and the mutant reports satisfied/accept; the
    # profile's scope says a float is cannot_establish/reject. It is wrong exactly where shortest-round-trip diverges.
    ("M18_FLOAT_ADMITTED_AS_SUPPORTED", "N14_FLOAT_PREIMAGE_VALUE_OUT_OF_SCOPE",
     "return type(value) is int and -MAX_SAFE_INT < value < MAX_SAFE_INT",
     "return type(value) in (int, float) and -MAX_SAFE_INT < value < MAX_SAFE_INT  # M18",
     "decision_ref_recompute_status"),
    # Reported by pipavlo82 on #48 (2026-09-21, tree-level pass). M19: authentic signed content under another Nostr kind is
    # accepted as a proof event. M20: declared preimage names are not required to be ASCII, so the stdlib key order (code
    # point) can silently differ from RFC 8785 (UTF-16 code unit). M21: a case the verifier could not evaluate rewrites the
    # observed outcome to "reject" instead of preserving what the implementation under test actually did.
    ("M19_EVENT_KIND_NOT_GATED", "N15_AUTHENTIC_EVENT_UNDER_WRONG_KIND",
     'if event["kind"] != PROOF_EVENT_KIND:  # M19', "if False:  # M19", "proof_event_status"),
    ("M20_NON_ASCII_NAMES_ACCEPTED", "N16_NON_ASCII_DECLARED_NAMES",
     "if not all(f.isascii() for f in declared):  # M20", "if False:  # M20", "decision_ref_recompute_status"),
    ("M21_INVALID_CASE_REWRITES_OBSERVED_TO_REJECT", "N17_INVALID_CASE_MUST_KEEP_OBSERVED_OUTCOME",
     '_supplied_observed(case), ["INVALID_CASE"])  # M21', '"reject", ["INVALID_CASE"])  # M21', "observed_verification_outcome"),
    # 2026-09-22 (MattyIceMatrix on #48, closing the N15/issuer_status split): a valid signature by a key that is
    # simply not the pinned one must be reported as a real, separate fact (issuer_status), not silently absorbed
    # into whether the signature itself checks out. M22 gates nothing on it.
    ("M22_ISSUER_NOT_GATED", "N18_AUTHENTIC_EVENT_UNDER_UNTRUSTED_KEY",
     'if event["pubkey"] != trusted_pubkey:  # M22', "if False:  # M22", "issuer_status"),
    # 2026-09-22 (pipavlo82 on #48): M19/M22 prove signature_status/issuer_status/proof_event_status are each
    # COMPUTED correctly in isolation, but neither proves the resulting status is actually load-bearing in
    # required_outcome()'s final conjunction -- a verifier could compute issuer_status/proof_event_status as
    # "violated" and still forget to require it for an accept, and neither existing mutant would catch that
    # class of bug. These two drop a conjunct from required_outcome() itself; both reuse a vector already in
    # the suite (N18, N15) rather than needing a new one, since those cases already isolate exactly one
    # dimension to "violated" with every other dimension "satisfied".
    ("M23_ISSUER_STATUS_NOT_GATING", "N18_AUTHENTIC_EVENT_UNDER_UNTRUSTED_KEY",
     'if signature == "satisfied" and issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     'if signature == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     "required_verification_outcome"),
    ("M24_PROOF_EVENT_STATUS_NOT_GATING", "N15_AUTHENTIC_EVENT_UNDER_WRONG_KIND",
     'if signature == "satisfied" and issuer == "satisfied" and proof_event == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     'if signature == "satisfied" and issuer == "satisfied" and schema == "satisfied" and recompute == "satisfied":  # M2/M8/M14/M22',
     "required_verification_outcome"),
]


DIMENSIONS = ("signature_status", "issuer_status", "proof_event_status", "preimage_schema_status",
              "decision_ref_recompute_status",
              "registered_set_completeness_status", "required_verification_outcome",
              "observed_verification_outcome", "verification_status")


def changed_dimensions(actual, expected):
    return [d for d in DIMENSIONS if actual[d] != expected[d]]


def main():
    if not MUTANTS:
        print(json.dumps({"status": "ZERO_MUTANTS", "total": 0}))
        return 2
    document = baseline.load_document(HERE / "vectors.json")
    registry, pubkey = document["registry"], document["trusted_pubkey"]
    cases = document["cases"]
    by_id = {c["case_id"]: c for c in cases}
    if any(baseline.evaluate(c, registry, pubkey) != c["expected"] for c in cases):
        print(json.dumps({"status": "BASELINE_FAILED"}))
        return 1
    if any(cid not in by_id for cid in CONTROLS) or by_id[CONTROLS[0]]["expected"]["required_verification_outcome"] != "accept" \
            or by_id[CONTROLS[1]]["expected"]["required_verification_outcome"] != "reject":
        print(json.dumps({"status": "INVALID_CONTROLS"}))
        return 1
    source = (HERE / "schema_check.py").read_text(encoding="utf-8")
    records = []
    for mutant in MUTANTS:
        name, killer, before, after, intended = mutant[:5]
        controls = mutant[5] if len(mutant) > 5 else CONTROLS
        entry = {"mutant": name, "required_killer": killer, "intended_dimension": intended, "controls": controls}
        if by_id.get(killer) is None or any(cid not in by_id for cid in controls):
            entry["status"] = "UNKNOWN_KILLER"
        elif source.count(before) != 1:
            entry["status"] = "NOT_APPLIED"
        else:
            try:
                ns = {"__name__": "schema_mutant", "_REGISTRY": registry}
                exec(compile(source.replace(before, after, 1), name, "exec"), ns)
                # Controls must be preserved on EVERY dimension except the one this mutant intentionally targets.
                controls_ok = all(
                    [d for d in changed_dimensions(ns["evaluate"](by_id[cid], registry, pubkey), by_id[cid]["expected"])
                     if d != intended] == []
                    for cid in controls)
                actual = ns["evaluate"](by_id[killer], registry, pubkey)
                changed = changed_dimensions(actual, by_id[killer]["expected"])
                killed = intended in changed
                entry.update(controls_preserved=controls_ok, changed_dimensions=changed,
                             also_changed=[d for d in changed if d != intended],
                             status="CONTROL_BROKEN" if not controls_ok else "KILLED" if killed else "SURVIVED")
            except Exception as error:
                entry.update(status="CRASH", error=type(error).__name__)
        records.append(entry)
    counts = {s: sum(r["status"] == s for r in records)
              for s in ("KILLED", "SURVIVED", "CRASH", "NOT_APPLIED", "CONTROL_BROKEN", "UNKNOWN_KILLER")}
    print(json.dumps({"mutations": records, "counts": counts, "controls": CONTROLS}, sort_keys=True, indent=2))
    return 0 if counts["KILLED"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
