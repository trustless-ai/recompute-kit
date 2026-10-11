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
    # Zexo on #59: subject_bound() computed its own verdict/grade without ever looking at the signature,
    # so check_decision() refusing c6 on "signature" did not stop subject_bound_check/evidence_grade from
    # still reporting NO_FINDING/AUTHENTICATED_REPORT for an unsigned report.
    ("M9_DROP_SIGNATURE_GUARD_IN_SUBJECT_BOUND", ["c6_manifest_signature_corrupted"],
     '    if not sig_valid: return "CANNOT_ESTABLISH", None                      # unsigned/corrupted report binds nothing\n',
     '    pass  # M9\n'),
    # Zexo + Pavlo on #59 (TAWG, 2026-10-07): a grade handed back WITH a refusal survived the whole suite on every refusal
    # branch but c6, and result_only() hard-wired to VALID survived because no vector had a non-clean scan. Killed now by
    # the verdict-wide invariant in evaluate() (only NO_FINDING / CONTRADICTED may carry a grade) and by c7.
    ('M10a_GRADE_ON_UNSIGNED_REFUSAL', ['c6_manifest_signature_corrupted'],
     '    if not sig_valid: return "CANNOT_ESTABLISH", None                      # unsigned/corrupted report binds nothing\n',
     '    if not sig_valid: return "CANNOT_ESTABLISH", "AUTHENTICATED_REPORT"                      # unsigned/corrupted report binds nothing  # M10a\n'),
    ('M10b_GRADE_ON_NOT_VALID_SCAN', ['c7_scan_result_not_clean'],
     '    if s.get("result") != "clean": return "NOT_VALID", None\n',
     '    if s.get("result") != "clean": return "NOT_VALID", "AUTHENTICATED_REPORT"  # M10b\n'),
    ('M10c_GRADE_ON_NO_SUBJECT', ['c1_scan_of_A_presented_with_B_unbound'],
     '    if subj is None: return "CANNOT_ESTABLISH", None                       # scan names no subject\n',
     '    if subj is None: return "CANNOT_ESTABLISH", "AUTHENTICATED_REPORT"                       # scan names no subject  # M10c\n'),
    ('M10d_GRADE_ON_K1_FREEZE', ['c5_k2_unordered_effective_digest'],
     '        return "CANNOT_ESTABLISH", None                                      # unordered effective digest: frozen to k=1\n',
     '        return "CANNOT_ESTABLISH", "AUTHENTICATED_REPORT"                                      # unordered effective digest: frozen to k=1  # M10d\n'),
    ('M10e_GRADE_ON_NON_HEREDITARY', ['c3c_scan_bound_to_root_subset_not_hereditary'],
     '            return "CANNOT_ESTABLISH", None                                  # corpus -> subset needs a hereditary scanner\n',
     '            return "CANNOT_ESTABLISH", "AUTHENTICATED_REPORT"                                  # corpus -> subset needs a hereditary scanner  # M10e\n'),
    ('M10f_GRADE_ON_MISSING_PROOFS', ['c3b_scan_bound_to_root_subset_no_proofs'],
     '        if not (cons and cons <= proved): return "CANNOT_ESTABLISH", None\n',
     '        if not (cons and cons <= proved): return "CANNOT_ESTABLISH", "AUTHENTICATED_REPORT"  # M10f\n'),
    ('M10g_GRADE_ON_SUBJECT_MISMATCH', ['c1b_scan_of_A_presented_with_B_bound'],
     '    else:\n        return "CANNOT_ESTABLISH", None\n',
     '    else:\n        return "CANNOT_ESTABLISH", "AUTHENTICATED_REPORT"  # M10g\n'),
    ('M11_RESULT_ONLY_ALWAYS_VALID', ['c7_scan_result_not_clean'],
     'def result_only(man): return "VALID" if man["body"]["rag_corpus"]["poisoning_scan"]["result"] == "clean" else "NOT_VALID"\n',
     'def result_only(man): return "VALID"  # M11\n'),
]
CONTROLS = ["c0_answer_flips_while_all_bindings_valid"]

def main():
    if not MUTANTS:
        print(json.dumps({"status": "ZERO_MUTANTS", "total": 0}))
        return 2
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
