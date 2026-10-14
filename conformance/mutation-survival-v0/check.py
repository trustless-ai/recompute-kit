#!/usr/bin/env python3
# Conformance for recompute-mutation-survival. The gate MUST tell load-bearing coverage from
# decorative coverage, and must NOT accept a mutant that died unobserved as a kill.
#
# The expectations live in mutation-survival-v0.vectors.json and this script READS them. They used
# to be bash literals here, which meant the vectors asserted nothing: inverting every expected_exit
# and expected_verdict, repinning the digest, and re-running still printed CONFORMANT — a decorative
# vector set shipped with the tool for catching decorative tests. (zexoverz, check:10, 2026-08-26)
#
# A .py file named by adapter.cmd and pinned as `checker`, with the tool it drives pinned under
# `dependencies`. It was an extensionless bash wrapper, which the runner's executable inventory
# (tokens ending in .py/.mjs/.cjs/.js/.ts) cannot see, so the code deciding this suite's verdict
# could change with every declared pin still matching. (pipavlo82, #17)
import json, os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
bin_ = os.path.join(here, "..", "..", "bin", "recompute-mutation-survival")
# Exit codes are the kit's tri-state, kept apart on purpose (zexoverz, #17 review, check:13):
#   1  a vector did not reproduce: the tool ran and answered differently from the expectation
#   2  could not run: no vectors, no tool, or no readable artifact, so nothing was compared
# One code for both delivers a could-not-run to run_conformance as returncode 1, which it classifies
# SUITE (a refuted vector). A determinate mismatch outranks a could-not-run, as in exit_code_for_failures.
try:
    spec = json.load(open(os.path.join(here, "mutation-survival-v0.vectors.json")))
    if not os.path.isfile(bin_): raise FileNotFoundError(bin_)
except Exception as e:
    print(f"mutation-survival-v0: UNVERIFIABLE (could not run: {type(e).__name__}: {e})")
    raise SystemExit(2)
# A self-grading check with nothing to grade prints CONFORMANT and exits 0 — the same
# absence-of-evidence class as ZERO_MUTANTS below it and ZERO_CASES across the kit's other
# self-graders. Same token, same exit, so the condition has one name everywhere.
if isinstance(spec.get("vectors"), list) and not spec["vectors"]:
    print("UNVERIFIABLE: ZERO_CASES", file=sys.stderr)
    raise SystemExit(2)
fail = norun = 0
def source_ref(d):
    # Derived here independently of the tool, so an artifact that drops or invents its ref goes red.
    head = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0:
        return None, None
    st = subprocess.run(["git", "-C", d, "status", "--porcelain", "--", "."], capture_output=True, text=True)
    return head.stdout.strip(), bool(st.stdout.strip())
for v in spec["vectors"]:
    d = os.path.join(here, v["fixture"])
    want_ref = source_ref(d)
    # per-vector override: the execution-freshness vector has to run under a test command that
    # does NOT hide staleness, which is the opposite of what the others want.
    tc = v.get("test_cmd", spec["test_cmd"])
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as t:
        art = t.name
    rc = subprocess.run([sys.executable, bin_, "--dir", d, "--test-cmd", tc,
                         "--mutations", os.path.join(d, "mutations.json"), "--out", art],
                        capture_output=True, text=True).returncode
    got_verdict = got_status = got_reason = None
    got = {}
    reasons = {}
    got_ref = ("<absent>", "<absent>")
    try:
        a = json.load(open(art))
        got_verdict = a.get("verdict")
        got_status, got_reason = a.get("status"), a.get("reason")
        reasons = {r.get("label"): r.get("reason") for r in a.get("results", [])}
        got_ref = (a.get("ref", "<absent>"), a.get("dirty", "<absent>"))
        got = {r.get("label"): r.get("verdict") for r in a.get("results", [])}
    except Exception as e:
        print(f"NORUN {v['name']:18} tool exit {rc}, artifact unreadable: {e}"); norun = 1
        continue
    finally:
        os.unlink(art)
    if rc not in (0, 1, 2):
        print(f"NORUN {v['name']:18} tool exit {rc} is outside the verdict contract"); norun = 1
        continue
    # expected_mutations pins EVERY mutant in the inventory, not one. A vector whose point is the
    # relation between consecutive mutants cannot be asserted one row at a time: pinning only the
    # second row lets a run that got the first row wrong still pass.
    want = v.get("expected_mutations") or ({v["mutation"]: v["expected_mutation"]}
                                           if v.get("mutation") else {})
    bad = []
    if rc != v["expected_exit"]:            bad.append(f"exit {rc} != {v['expected_exit']}")
    if got_verdict != v["expected_verdict"]: bad.append(f"verdict {got_verdict!r} != {v['expected_verdict']!r}")
    # Why a run or a row was unverifiable is part of the answer: one marker reachable from several
    # causes passes this check for the wrong one unless the cause is pinned too.
    if got_status != v.get("expected_status"):
        bad.append(f"status {got_status!r} != {v.get('expected_status')!r}")
    if got_reason != v.get("expected_reason"):
        bad.append(f"reason {got_reason!r} != {v.get('expected_reason')!r}")
    for label, exp in (v.get("expected_reasons") or {}).items():
        if reasons.get(label) != exp:
            bad.append(f"reason of {label!r} {reasons.get(label)!r} != {exp!r}")
    if got_ref != want_ref:                  bad.append(f"ref/dirty {got_ref!r} != {want_ref!r}")
    for label, exp in want.items():
        if got.get(label) != exp:
            bad.append(f"mutation {label!r} {got.get(label)!r} != {exp!r}")
    if v.get("expected_no_results") and got:
        bad.append(f"expected no mutation results, got {sorted(got)}")
    if bad:
        print(f"FAIL {v['name']:18} " + "; ".join(bad)); fail = 1
    else:
        shown = ", ".join(f"{k}={vv}" for k, vv in sorted(got.items())) or "no mutants"
        print(f"OK   {v['name']:18} exit {rc}, {got_verdict}, {shown}")
print("mutation-survival-v0: " + ("NON-CONFORMANT" if fail else
                                  "UNVERIFIABLE (a vector could not run)" if norun else "CONFORMANT"))
sys.exit(1 if fail else (2 if norun else 0))
