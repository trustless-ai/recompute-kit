"""Regression: an entry in conformance/uncovered.json must be reported STALE once the suite it
excuses starts running — for multi-check suites as well as single-check ones.

`uncovered.json` holds suite DIRECTORY names. A single-check suite reports one result labelled
with that bare name; a multi-check suite reports one result per check, labelled
"<dir>/<check>" (e.g. "permission-consumption-boundary-v0/conformance"). The stale sweep used to
compare the full result label to the directory name, so it could only ever fire for
single-check suites: an uncovered entry for a multi-check suite stayed on the list after the
suite began running, which is precisely the drift the list's own header says it must catch.

Both sides matter (the no-silent-skips invariant):
  - a declared suite that now runs, single-check OR multi-check -> reported stale, once;
  - a declared suite that still does not run -> relabelled NOT RUN, never stale;
  - an undeclared suite, and a directory that merely shares a prefix with a declared one,
    -> never stale.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_conformance as runner  # noqa: E402

R = runner.Result


class SuiteDirTests(unittest.TestCase):
    def test_bare_label_is_its_own_dir(self):
        self.assertEqual(runner.suite_dir("aggregate-budget-v0"), "aggregate-budget-v0")

    def test_check_suffix_is_stripped(self):
        self.assertEqual(runner.suite_dir("permission-consumption-boundary-v0/conformance"),
                         "permission-consumption-boundary-v0")

    def test_only_first_separator_splits(self):
        self.assertEqual(runner.suite_dir("a/b/c"), "a")


class StaleDeclarationTests(unittest.TestCase):
    def test_single_check_suite_now_running_is_stale(self):
        # the behaviour that already worked — guarded so the fix cannot regress it
        results = [R("aggregate-budget-v0", True, "SUITE", "ok")]
        self.assertEqual(runner.classify_declared_uncovered(results, {"aggregate-budget-v0"}, set()),
                         ["aggregate-budget-v0"])

    def test_multi_check_suite_now_running_is_stale_once(self):
        # the bug: labels are "<dir>/<check>", so a label-vs-dir comparison never matched
        results = [R("perm-v0/conformance", True, "SUITE", "ok"),
                   R("perm-v0/mutation-coverage", True, "SUITE", "ok")]
        self.assertEqual(runner.classify_declared_uncovered(results, {"perm-v0"}, set()), ["perm-v0"])

    def test_multi_check_suite_failing_is_still_stale(self):
        # declared uncovered but it runs (and fails): the exclusion is false either way
        results = [R("perm-v0/conformance", False, "SUITE", "refuted"),
                   R("perm-v0/mutation-coverage", True, "SUITE", "ok")]
        self.assertEqual(runner.classify_declared_uncovered(results, {"perm-v0"}, set()), ["perm-v0"])

    def test_declared_suite_that_does_not_run_is_relabelled_not_stale(self):
        r = R("no-suite-v0", False, "NOT COVERED", "no suite.json")
        stale = runner.classify_declared_uncovered([r], {"no-suite-v0"}, set())
        self.assertEqual(stale, [])
        self.assertEqual(r.kind, "DECLARED UNCOVERED")

    def test_undeclared_suite_is_never_stale(self):
        results = [R("other-v0/conformance", True, "SUITE", "ok"), R("plain-v0", True, "SUITE", "ok")]
        self.assertEqual(runner.classify_declared_uncovered(results, {"perm-v0"}, set()), [])

    def test_shared_prefix_is_not_a_match(self):
        # "perm-v0-extra" merely starts with the declared "perm-v0": a different directory
        results = [R("perm-v0-extra/conformance", True, "SUITE", "ok")]
        self.assertEqual(runner.classify_declared_uncovered(results, {"perm-v0"}, set()), [])

    def test_undeclared_vectors_relabel_is_unchanged(self):
        r = R("vecs-v0", False, "UNDECLARED", "vector files nobody runs")
        stale = runner.classify_declared_uncovered([r], set(), {"vecs-v0"})
        self.assertEqual(stale, [])
        self.assertEqual(r.kind, "DECLARED UNCOVERED")


if __name__ == "__main__":
    unittest.main()
