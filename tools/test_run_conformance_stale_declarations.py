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
import pathlib
import shlex
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_runtime_precondition_stop_is_not_stale_and_not_excused(self):
        # a missing runtime dependency stops the adapter before it runs (#69): the suite is still
        # unrun, so its entry is not stale -- and the RUNNER failure keeps failing the build
        r = R("perm-v0/conformance", False, "RUNNER",
              "precondition: runtime dependency missing (node), adapter not run", adapter_ran=False)
        self.assertEqual(runner.classify_declared_uncovered([r], {"perm-v0"}, set()), [])
        self.assertEqual(r.kind, "RUNNER")

    def test_precondition_guard_reads_the_producers_actual_result_not_its_wording(self):
        # producer -> consumer on the REAL path: _run_one stops on a missing module before the adapter
        # runs. Rewording that message (TMerlini's #52 review: "unmet precondition: ...") must not turn
        # an unrun suite into a stale one, and must not drop the RUNNER cause.
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp) / "perm-v0"
            d.mkdir()
            (d / "adapter.py").write_text("import rfc8785_not_installed_xyz\n", encoding="utf-8")
            m = {"adapter": {"kind": "stdio", "contract": "self_grading",
                             "cmd": f"{shlex.quote(sys.executable)} adapter.py"},
                 "runtime": {"python_modules": ["rfc8785_not_installed_xyz"]}}
            with mock.patch.object(runner.subprocess, "run", side_effect=AssertionError("adapter must not run")):
                r = runner._run_one(d, m, "perm-v0/conformance")
        self.assertEqual(r.kind, "RUNNER")
        self.assertIs(r.adapter_ran, False)
        r.detail = "unmet precondition: runtime dependency missing (rfc8785_not_installed_xyz), adapter not run"
        self.assertEqual(runner.classify_declared_uncovered([r], {"perm-v0"}, set()), [])
        self.assertEqual(r.kind, "RUNNER")

    def test_precondition_wording_alone_does_not_excuse_a_suite_that_ran(self):
        # the prose is not the marker: a RUNNER result whose adapter ran is stale whatever its detail says
        r = R("perm-v0/conformance", False, "RUNNER", "precondition: looks like one, but the adapter ran")
        self.assertEqual(runner.classify_declared_uncovered([r], {"perm-v0"}, set()), ["perm-v0"])

    def test_runner_failure_after_the_adapter_ran_is_still_stale(self):
        # a timeout is a RUNNER failure too, but the adapter did run: the exclusion is false
        results = [R("perm-v0/conformance", False, "RUNNER", "timed out after 300s")]
        self.assertEqual(runner.classify_declared_uncovered(results, {"perm-v0"}, set()), ["perm-v0"])

    def test_declared_suite_that_does_not_run_is_relabelled_not_stale(self):
        r = R("no-suite-v0", False, "NOT COVERED", "no suite.json")
        stale = runner.classify_declared_uncovered([r], {"no-suite-v0"}, set())
        self.assertEqual(stale, [])
        self.assertEqual(r.kind, "DECLARED UNCOVERED")

    def test_declared_directory_excuses_its_multi_check_not_covered_result(self):
        # matching on the directory also widens what the list excuses (#52 review): a multi-check
        # result that is NOT COVERED under a declared directory is relabelled, not left failing
        r = R("no-suite-v0/conformance", False, "NOT COVERED", "declares no adapter.cmd")
        self.assertEqual(runner.classify_declared_uncovered([r], {"no-suite-v0"}, set()), [])
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
