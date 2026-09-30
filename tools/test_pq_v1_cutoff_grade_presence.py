#!/usr/bin/env python3
"""pq_key_binding.v1 — pins that grade() asserts PRESENCE, not just value, on declared-null fields.

The bug this guards: `got.get(k) != exp[k]` returns None for both "key present with value None" and
"key absent entirely" — grading by that comparison alone cannot tell a checker that stopped emitting
a field apart from one that emitted it as null. 13 of the 26 v1 cutoff vectors declare
`resolved: null` (the null-resolution cases — pre_baseline, no_in_force_binding, and the various
unverifiable/refuted chain-failure branches), so a mutant that drops `resolved` from the checker's
return value on any of those paths would satisfy every one of them under the old comparison.

Two halves, because a mutation test that cannot fail on the pre-fix code proves nothing:

  CONTROL   the pre-fix comparison (`got.get(k) != exp[k]`) accepts the mutant — proves the bug
            was real, not hypothetical.
  FIX       the current grade() rejects the same mutant — proves the fix closes exactly this gap.

Run: python3 tools/test_pq_v1_cutoff_grade_presence.py   -> exit 0 claim holds, 1 otherwise.
"""
import importlib.util
import json
import pathlib
import sys

SUITE = pathlib.Path(__file__).resolve().parent.parent / "conformance" / "pq-key-binding-v1"


def load_enforcer():
    spec = importlib.util.spec_from_file_location("cutoff_enforce_v1", SUITE / "cutoff_enforce.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pre_fix_grade(got, exp, discriminating):
    """The whitelist-free but presence-blind comparison grade() carried before this fix."""
    diffs = [(k, got.get(k), exp[k]) for k in exp if got.get(k) != exp[k]]
    diffs += [(k, got.get(k), "<absent>") for k in discriminating if k not in exp and k in got]
    return diffs


def main():
    ce = load_enforcer()
    fx = json.load(open(SUITE / "pq-key-binding-v1.cutoff-vectors.json"))
    null_resolved_cases = [c for c in fx["cases"] if c["expected"].get("resolved") is None]

    failures = []
    print(f"{len(null_resolved_cases)} of {len(fx['cases'])} cases declare resolved: null")

    if not null_resolved_cases:
        failures.append("no declared-null case found — this probe would be vacuous; fix the fixture path")

    control_missed = 0
    fix_caught = 0
    for c in null_resolved_cases:
        exp = c["expected"]
        # Simulate a checker regression: same verdict, but the declared-null field is missing
        # entirely rather than present-as-None.
        mutant_got = {k: v for k, v in exp.items() if k != "resolved"}
        assert "resolved" not in mutant_got

        pre_diffs = pre_fix_grade(mutant_got, exp, ce.DISCRIMINATING)
        post_diffs = ce.grade(mutant_got, exp)

        if not pre_diffs:
            control_missed += 1
        if post_diffs:
            fix_caught += 1
        else:
            print(f"    FIX MISSED: {c['name']!r} — mutant with resolved absent was not flagged")

    print(f"CONTROL (pre-fix logic): missed the absent-field mutant on {control_missed}/"
          f"{len(null_resolved_cases)} declared-null cases")
    print(f"FIX     (current grade): caught the absent-field mutant on {fix_caught}/"
          f"{len(null_resolved_cases)} declared-null cases")

    if control_missed == 0:
        failures.append(
            "the CONTROL caught every mutant under the pre-fix comparison too — the bug this test "
            "targets may already be gone by a different path, or this probe is not constructing the "
            "case it claims to. Either way the control here is not proving anything."
        )
    if fix_caught != len(null_resolved_cases):
        failures.append(
            f"the current grade() still misses {len(null_resolved_cases) - fix_caught} declared-null "
            "case(s) when the field is dropped entirely — the presence-vs-value gap is not fully closed."
        )

    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        return 1
    print("claim holds: the pre-fix comparison missed every absent-field mutant on declared-null "
          "cases, and the current grade() catches every one of them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
