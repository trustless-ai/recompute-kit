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
    ("M8_MISSING_EVIDENCE_BECOMES_AUTHORIZED", ["P12", "P13", "P14", "P16", "P21"],
     'status = combine(current)  # M8',
     'status = "satisfied" if combine(current) == "cannot_establish" else combine(current)  # M8'),
    ("M9_IGNORE_GRANT_IDENTITY_MISMATCH", ["P17", "P18"],
     '    if identity(consume) != identity(selected):\n'
     '        return result("satisfied", "violated", observed, historical, {}, ["GRANT_IDENTITY_MISMATCH"])\n',
     ''),
    ("M10_IGNORE_CAPACITY_DOMAIN_MISMATCH", ["P19"],
     '    if consume["capacity_domain"] != selected["capacity_domain"]:\n'
     '        return result("satisfied", "violated", observed, historical, {}, ["CAPACITY_DOMAIN_MISMATCH"])\n',
     ''),
    # Field-specific witnesses (pipavlo82 on #50): these mutants move a status or the evaluation order, not the final
    # decision, so "reject -> admit" can never witness them. Their witness predicate names the field that must move.
    ("M11_EVALUATE_CURRENT_AFTER_HISTORICAL_FAILURE", ["P15"],
     '    if historical_status != "satisfied":\n',
     '    if False:  # M11\n',
     "current_evaluated"),
    ("M12_UNKNOWN_OUTRANKS_VIOLATION", ["P20"],
     '    return ("violated" if "violated" in values else\n'
     '            "cannot_establish" if "cannot_establish" in values else "satisfied")\n',
     '    return ("cannot_establish" if "cannot_establish" in values else\n'
     '            "violated" if "violated" in values else "satisfied")  # M12\n',
     "violated_to_cannot_establish"),
]


def witness(kind, expected, actual):
    """Does this killer case witness the mutant? kind names the field that must move."""
    same_history = (actual["historical_check_status"] == expected["historical_check_status"]
                    and actual["historical_components"] == expected["historical_components"]
                    and actual["observed_consumption_outcome"] == expected["observed_consumption_outcome"])
    if kind == "reject_to_admit":
        return (expected["current_authorization_status"] in {"violated", "cannot_establish"}
                and expected["required_consumption_outcome"] == "reject"
                and actual["current_authorization_status"] == "satisfied"
                and actual["required_consumption_outcome"] == "admit" and same_history)
    if kind == "current_evaluated":
        # the historical failure must still be reported, but current authorization got evaluated anyway
        return (expected["current_components"] == {} and actual["current_components"] != {}
                and "CURRENT_AUTHORIZATION_NOT_EVALUATED" not in actual["reason_codes"] and same_history)
    if kind == "violated_to_cannot_establish":
        return (expected["current_authorization_status"] == "violated"
                and actual["current_authorization_status"] == "cannot_establish"
                and actual["current_components"] == expected["current_components"])
    raise ValueError(f"unknown witness kind {kind!r}")


def main():
    if not MUTANTS:
        print(json.dumps({"status": "ZERO_MUTANTS", "total": 0}))
        return 2
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
    for name, prefixes, before, after, *kind in MUTANTS:
        kind = kind[0] if kind else "reject_to_admit"
        killers = [next(cid for cid in by_id if cid.split("_")[0] == p) for p in prefixes]
        record = {"mutant": name, "required_killers": killers, "witness_kind": kind, "applied": False, "executed": False}
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
                witnesses = {k: witness(kind, by_id[k]["expected"], outputs[k]) for k in killers}
                # every case whose output moved: a required killer proves the intended case moved, not that
                # nothing unrelated did -- recorded so an exclusivity claim can be checked, never assumed
                changed = sorted(cid for cid in by_id if outputs[cid] != by_id[cid]["expected"])
                record.update(changed_cases=changed, unexpected_changes=sorted(set(changed) - set(killers)))
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
