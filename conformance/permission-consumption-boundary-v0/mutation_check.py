#!/usr/bin/env python3
"""One-site source mutations; required witnesses, no crash or control-failure kills."""

import json
from pathlib import Path
import sys

import permission_check as baseline

HERE = Path(__file__).resolve().parent
CURRENT = 'current = components(data, grant, consume["at"], consume["evidence"])  # current composition'
MUTANTS = [
    ("M1_TRUST_HISTORICAL_PASS", ["P3", "P5", "P9"],
     CURRENT,
     'current = historical.copy()  # M1'),
    ("M2_CHECK_EXPIRY_ONLY_AT_CHECK_TIME", ["P3", "P4"],
     'expiry_time = at  # M2:', 'expiry_time = data["check_at"]  # M2:'),
    ("M3_IGNORE_CURRENT_LIFECYCLE", ["P5"],
     CURRENT, CURRENT + '\n        current["lifecycle"] = "satisfied"'),
    ("M4_ALLOW_RENEWED_EPOCH_SUBSTITUTION", ["P7"],
     'and g["grant_epoch"] == selected["grant_epoch"]]  # M4', 'and True]  # M4'),
    ("M5_ALLOW_UNRELATED_GRANT_SUBSTITUTION", ["P8"],
     'if g["grant_id"] == selected["grant_id"]  # M5', 'if True  # M5'),
    ("M6_IGNORE_CURRENT_CAPACITY", ["P9"],
     CURRENT, CURRENT + '\n        current["capacity"] = "satisfied"'),
    ("M7_ALLOW_WRONG_CAPACITY_DOMAIN", ["P11"],
     'if d["domain_id"] == grant["capacity_domain"]]  # M7', 'if True]  # M7'),
    ("M8_MISSING_EVIDENCE_BECOMES_AUTHORIZED", ["P12", "P13", "P14"],
     'status = combine(current)  # M8',
     'status = "satisfied" if combine(current) == "cannot_establish" else combine(current)  # M8'),
    ("M9_ALLOW_CONSUMED_IDENTITY_MISMATCH", ["P17", "P18"],
     'if identity(consume) != identity(selected):  # M9', 'if False:  # M9'),
    ("M10_ALLOW_CONSUMED_CAPACITY_DOMAIN_MISMATCH", ["P19"],
     'if consume["capacity_domain"] != selected["capacity_domain"]:  # M10', 'if False:  # M10'),
]


def main():
    cases = baseline.load_cases(HERE / "vectors.json")
    if any(baseline.evaluate(c) != c["expected"] for c in cases) or not all(baseline.assertions(cases).values()):
        print(json.dumps({"status": "BASELINE_FAILED"}))
        return 1
    by_id = {c["case_id"]: c for c in cases}
    controls = [c for c in cases if c["expected"]["historical_check_status"] == "satisfied"
                and c["expected"]["current_authorization_status"] == "satisfied"
                and c["expected"]["observed_consumption_outcome"] == "admit"]
    if {c["case_id"].split("_")[0] for c in controls} != {"P1", "P2", "P10", "P22"}:
        print(json.dumps({"status": "INVALID_CONTROLS"}))
        return 1
    source = (HERE / "permission_check.py").read_text(encoding="utf-8")
    records = []
    for name, prefixes, before, after in MUTANTS:
        killers = [next(cid for cid in by_id if cid.split("_")[0] == p) for p in prefixes]
        record = {"mutant": name, "required_killers": killers, "applied": False, "executed": False}
        if source.count(before) != 1:
            record["status"] = "NOT_APPLIED"
        else:
            record["applied"] = True
            try:
                ns = {"__name__": "permission_mutant", "__file__": str(HERE / "permission_check.py")}
                exec(compile(source.replace(before, after, 1), name, "exec"), ns)
                outputs = {c["case_id"]: ns["evaluate"](c) for c in cases}
                record["executed"] = True
                controls_ok = all(outputs[c["case_id"]] == c["expected"] for c in controls)
                witnesses = {}
                for killer in killers:
                    expected, actual = by_id[killer]["expected"], outputs[killer]
                    witnesses[killer] = (
                        expected["current_authorization_status"] in {"violated", "cannot_establish"}
                        and expected["required_consumption_outcome"] == "reject"
                        and actual["current_authorization_status"] == "satisfied"
                        and actual["required_consumption_outcome"] == "admit"
                        and actual["historical_check_status"] == expected["historical_check_status"]
                        and actual["historical_components"] == expected["historical_components"]
                        and actual["observed_consumption_outcome"] == expected["observed_consumption_outcome"])
                record.update(controls_preserved=controls_ok, witnesses=witnesses,
                              witness_results={cid: outputs[cid] for cid in killers},
                              status="CONTROL_BROKEN" if not controls_ok else
                              "KILLED" if all(witnesses.values()) else "SURVIVED")
            except Exception as error:
                record.update(status="CRASH", error=type(error).__name__)
        records.append(record)
    counts = {s: sum(r["status"] == s for r in records)
              for s in ("KILLED", "SURVIVED", "CRASH", "NOT_APPLIED", "CONTROL_BROKEN")}
    print(json.dumps({"mutations": records, "counts": counts,
                      "positive_controls": [c["case_id"] for c in controls]}, sort_keys=True, indent=2))
    return 0 if counts["KILLED"] == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
