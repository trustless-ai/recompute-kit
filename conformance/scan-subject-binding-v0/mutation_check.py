#!/usr/bin/env python3
"""One-site source mutations of scan_check.py; each must be killed by its required case(s) while the positive control holds.
Also two primitive controls: the stdlib Ed25519 verify rejects a tampered signature and a wrong key."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RETURN_REPORT = '    return "NO_FINDING", "AUTHENTICATED_REPORT"                            # signed report over a bound subject, not rerun\n'
MUTANTS = [
    ("M1_IGNORE_SUBJECT_DIGEST_TRUST_CLEAN", ["c1_scan_of_A_presented_with_B_unbound", "c1b_scan_of_A_presented_with_B_bound"],
     '    if s.get("result") != "clean": return "NOT_VALID", None\n',
     '    if s.get("result") != "clean": return "NOT_VALID", None\n    return "NO_FINDING", "AUTHENTICATED_REPORT"  # M1\n'),
    ("M2_PROMOTE_NO_FINDING_TO_POISONING_ABSENT", ["c2_scan_bound_to_consumed_effective_dataset", "c3_scan_bound_to_root_subset_with_proofs"],
     RETURN_REPORT, '    return "POISONING_ABSENT", "AUTHENTICATED_REPORT"  # M2\n'),
    ("M3_IGNORE_SCANNER_SEMANTICS", ["c3c_scan_bound_to_root_subset_not_hereditary"],
     '        if s.get("semantics") != "recordwise":\n', '        if False:  # M3\n'),
    ("M4_GRADE_REPORT_AS_REPRODUCED", ["c2_scan_bound_to_consumed_effective_dataset", "c3_scan_bound_to_root_subset_with_proofs"],
     RETURN_REPORT, '    return "NO_FINDING", "REPRODUCED"  # M4\n'),
    ("M5_IGNORE_K1_FREEZE", ["c5_k2_unordered_effective_digest"],
     '    if dec.get("k", 1) != 1 or len(dec["retrieved"]) != 1:\n', '    if False:  # M5\n'),
    ("M6_TRUST_SIGNED_CLEAN_OVER_RERUN", ["c4b_reproduced_contradicts_signed_clean", "c4_reproduced_clean"],
     '    if s.get("scanner_version") == toy["scanner_version"]:\n', '    if False:  # M6\n'),
    ("M7_SKIP_INCLUSION_PROOFS", ["c3b_scan_bound_to_root_subset_no_proofs"],
     '        if not (cons and cons <= proved): return "CANNOT_ESTABLISH", None\n', '        pass  # M7\n'),
    # Pavlo on #56: the primitive controls test ed25519_verify directly, not that check_decision() calls it.
    ("M8_DROP_SIGNATURE_GUARD_IN_CHECK_DECISION", ["c6_manifest_signature_corrupted"],
     '    if not sig_ok(pub, man): f.append("signature")\n', '    pass  # M8\n'),
]
CONTROLS = ["c0_answer_flips_while_all_bindings_valid"]

def main():
    import scan_check as base
    V, pub, toy = base.load(HERE / "vectors.json")
    cases = dict(sorted(V["cases"].items()))
    # primitive controls on the signature check itself
    m = next(c for n, c in cases.items() if not n.startswith("c0"))["manifest"]
    msg = b"scan-subject-binding-v0\n" + base.canon(m["body"]); sig = bytearray(bytes.fromhex(m["sig"])); sig[5] ^= 1
    prim = {"signature_verifies": base.ed25519_verify(pub, bytes.fromhex(m["sig"]), msg),
            "tampered_signature_rejected": not base.ed25519_verify(pub, bytes(sig), msg),
            "wrong_key_rejected": not base.ed25519_verify(bytes(32), bytes.fromhex(m["sig"]), msg)}
    source = (HERE / "scan_check.py").read_text(encoding="utf-8")
    records = []
    for name, killers, before, after in MUTANTS:
        rec = {"mutant": name, "required_killers": killers, "applied": False, "executed": False}
        if source.count(before) != 1:
            rec["status"] = "NOT_APPLIED"
        else:
            rec["applied"] = True
            try:
                ns = {"__name__": "scan_mutant", "__file__": str(HERE / "scan_check.py")}
                exec(compile(source.replace(before, after, 1), name, "exec"), ns)
                ok = {n: ns["evaluate"](n, c, pub, toy)[1] for n, c in cases.items()}
                rec["executed"] = True
                controls_ok = all(ok[n] for n in CONTROLS)
                witnesses = {k: not ok[k] for k in killers}
                changed = sorted(n for n in cases if not ok[n])
                rec.update(controls_preserved=controls_ok, witnesses=witnesses, changed_cases=changed,
                           unexpected_changes=sorted(set(changed) - set(killers)),
                           status="CONTROL_BROKEN" if not controls_ok else "KILLED" if all(witnesses.values()) else "SURVIVED")
            except Exception as error:
                rec.update(status="CRASH", error=type(error).__name__)
        records.append(rec)
    counts = {s: sum(r["status"] == s for r in records) for s in ("KILLED", "SURVIVED", "CRASH", "NOT_APPLIED", "CONTROL_BROKEN")}
    print(json.dumps({"mutations": records, "counts": counts, "positive_controls": CONTROLS, "primitive_controls": prim},
                     sort_keys=True, indent=2))
    return 0 if counts["KILLED"] == len(MUTANTS) and all(prim.values()) else 1

if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main())
