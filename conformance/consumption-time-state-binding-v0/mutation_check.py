#!/usr/bin/env python3
"""One-site oracle mutations: named required-decision witnesses, no crash kills."""

import json
from pathlib import Path
import sys

import binding_check as baseline

HERE = Path(__file__).resolve().parent
CONTROLS = ["S1_CONTROL_UNCHANGED_STATE", "S5_STATE_CHANGED_BUT_PREDICATE_STILL_TRUE_REEVALUATE",
            "S15_UNBOUND_UNCHANGED_STATE"]
MUTANTS = [
    ("M1_OLD_PASS_IS_CONSUMPTION_AUTHORITY", "S2_STALE_PASS_AFTER_STATE_CHANGE_UNBOUND",
     'if record["checked_state_version"] != state["state_version"]:  # M1', 'if False:  # M1'),
    ("M2_VERSION_BINDING_REMOVED", "S3_VERSION_BOUND_REJECTS_STALE",
     'if record["checked_state_version"] != state["state_version"]:  # M2/M7', 'if False:  # M2/M7'),
    ("M3_REEVALUATION_REMOVED", "S4_REEVALUATE_REJECTS_STALE_FALSE",
     'if predicate(state, amount):  # M3:', 'if record["predicate_result"]:  # M3:'),
    ("M4_EVENT_FALSE_CAN_BE_CONSUMED", "S7_EVENT_TIME_FALSE",
     'if not record["predicate_result"]:  # M4:', 'if False:  # M4:'),
    ("M5_CHECK_STATE_IDENTITY_NOT_BOUND", "S9_CHECK_STATE_COORDINATE_TAMPER",
     'if supplied != record:  # M5:', 'if False:  # M5:'),
    ("M6_REQUEST_SCOPE_NOT_BOUND", "S10_WRONG_REQUEST_REUSE",
     'if amount != record["amount"]:  # M6:', 'if False:  # M6:'),
    ("M7_STATE_VALUE_EQUALITY_TREATED_AS_STATE_IDENTITY", "S11_ABA_VALUE_EQUALITY_NOT_STATE_IDENTITY",
     'if record["checked_state_version"] != state["state_version"]:  # M2/M7',
     'if (record["checked_used"], record["checked_ceiling"]) != (state["used"], state["ceiling"]):  # M2/M7'),
]


def main():
    if not MUTANTS:
        print(json.dumps({"status": "ZERO_MUTANTS", "total": 0}))
        return 2
    cases = baseline.load_cases(HERE / "vectors.json")
    by_id = {c["case_id"]: c for c in cases}
    if any(baseline.evaluate(c) != c["expected"] for c in cases):
        print(json.dumps({"status": "BASELINE_FAILED"}))
        return 1
    if any(cid not in by_id or by_id[cid]["expected"]["required_consumption_outcome"] != "admit"
           or by_id[cid]["expected"]["consumption_time_status"] != "satisfied" for cid in CONTROLS):
        print(json.dumps({"status": "INVALID_POSITIVE_CONTROLS"}))
        return 1
    source = (HERE / "binding_check.py").read_text(encoding="utf-8")
    records = []
    for name, killer, before, after in MUTANTS:
        entry = {"mutant": name, "required_killer": killer, "axis": "required_consumption_outcome"}
        if source.count(before) != 1:
            entry["status"] = "NOT_APPLIED"
        else:
            try:
                ns = {"__name__": "binding_mutant"}
                exec(compile(source.replace(before, after, 1), name, "exec"), ns)
                outputs = {c["case_id"]: ns["evaluate"](c) for c in cases}
                controls_ok = all(outputs[cid] == by_id[cid]["expected"] for cid in CONTROLS)
                expected, actual = by_id[killer]["expected"], outputs[killer]
                killed = (expected["required_consumption_outcome"] == "reject"
                          and actual["required_consumption_outcome"] == "admit"
                          and actual["observed_results"] == expected["observed_results"]
                          and actual["event_time_status"] == expected["event_time_status"]
                          and actual["checked_state_version"] == expected["checked_state_version"]
                          and actual["current_state_version"] == expected["current_state_version"])
                entry.update(controls_preserved=controls_ok, witness_result=actual,
                             status="CONTROL_BROKEN" if not controls_ok else "KILLED" if killed else "SURVIVED")
            except Exception as error:
                entry.update(status="CRASH", error=type(error).__name__)
        records.append(entry)
    counts = {s: sum(r["status"] == s for r in records)
              for s in ("KILLED", "SURVIVED", "CRASH", "NOT_APPLIED", "CONTROL_BROKEN")}
    print(json.dumps({"mutations": records, "counts": counts, "positive_controls": CONTROLS}, sort_keys=True, indent=2))
    return 0 if counts["KILLED"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
