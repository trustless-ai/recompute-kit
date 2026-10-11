#!/usr/bin/env python3
"""Real source mutations, required negative witnesses, preserved safe controls."""

import json
from pathlib import Path
import sys

import boundary_check as baseline

HERE = Path(__file__).resolve().parent
# Each patch must occur exactly once. No runtime mutant flag in the checker.
MUTANTS = [
    ("M1_PERIODIC_PASS_IS_AUTHORITY", "A2_PERIODIC_PASS_BECOMES_STALE", "event_time_status",
     'event_bad.add("PERIODIC_PASS_NOT_AUTHORITY")', 'pass'),
    ("M2_EVENT_REEVALUATION_REMOVED", "D1_EVENT_CHECK_REMOVED", "event_time_status",
     'event_bad.add("EVENT_CHECK_MISSING")', 'pass'),
    ("M3_ATOMIC_COMPARE_REMOVED", "D2_STALE_CAS_COMMIT", "concurrency_status",
     'if expected != version:  # M3/M5:', 'if False:  # M3/M5:'),
    ("M4_IDEMPOTENCY_IS_ATOMICITY", "B6_DISTINCT_REQUEST_RACE", "concurrency_status",
     'elif discipline == "UNSPECIFIED":',
     'elif keyed:\n                    pass  # incorrectly substitute identity lookup for exclusion\n                elif discipline == "UNSPECIFIED":'),
    ("M5_ADVANCED_VERSION_ALLOWED", "D2_STALE_CAS_COMMIT", "concurrency_status",
     'if expected != version:  # M3/M5:', 'if expected > version:  # M3/M5:'),
    ("M6_SERIALIZATION_ASSUMED", "D3_SERIALIZATION_OVERLAP", "concurrency_status",
     'if discipline != "UNSPECIFIED":  # M6:', 'if False:  # M6:'),
    ("M7_NONOVERLAP_TREATED_AS_CONCURRENT", "D12_PRIOR_OVERLAP_DOES_NOT_TAINT_LATER_WRITER", "concurrency_status",
     'if attempt["overlapped"]:  # M4/M7:', 'if True:  # M4/M7:'),
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
    axes = ("event_time_status", "concurrency_status", "idempotency_status")
    # All fully safe cases, including correct predicate rejection, are controls.
    controls = [c for c in cases if all(c["expected"][a] in ("satisfied", "not_applicable") for a in axes)]
    if not controls or not any(c["expected"]["admission_result"] == "admit" for c in controls):
        print(json.dumps({"status": "NO_POSITIVE_CONTROLS"}))
        return 1
    source = (HERE / "boundary_check.py").read_text(encoding="utf-8")
    report = []
    for name, killer, axis, before, after in MUTANTS:
        record = {"mutant": name, "required_killer": killer, "axis": axis}
        if source.count(before) != 1:
            record["status"] = "NOT_APPLIED"
        else:
            try:
                namespace = {"__name__": "boundary_mutant", "__file__": str(HERE / "boundary_check.py")}
                exec(compile(source.replace(before, after, 1), name, "exec"), namespace)
                evaluate = namespace["evaluate"]
                outputs = {c["case_id"]: evaluate(c) for c in cases}
                control_ok = all(outputs[c["case_id"]] == c["expected"] for c in controls)
                expected_status, mutant_status = (("cannot_establish", "violated")
                                                  if name == "M7_NONOVERLAP_TREATED_AS_CONCURRENT"
                                                  else ("violated", "satisfied"))
                witnessed = (by_id[killer]["expected"][axis] == expected_status
                             and outputs[killer][axis] == mutant_status
                             and outputs[killer]["transition_count"] == by_id[killer]["expected"]["transition_count"])
                record["controls_preserved"] = control_ok
                record["witness_result"] = outputs[killer]
                record["status"] = ("CONTROL_BROKEN" if not control_ok else
                                    "KILLED" if witnessed else "SURVIVED")
            except Exception as error:
                record["status"] = "CRASH"
                record["error"] = type(error).__name__
        report.append(record)
    counts = {s: sum(r["status"] == s for r in report)
              for s in ("KILLED", "SURVIVED", "CRASH", "NOT_APPLIED", "CONTROL_BROKEN")}
    print(json.dumps({"mutations": report, "counts": counts,
                      "positive_controls": [c["case_id"] for c in controls]}, sort_keys=True, indent=2))
    return 0 if counts["KILLED"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
