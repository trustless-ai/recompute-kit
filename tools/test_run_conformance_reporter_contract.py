#!/usr/bin/env python3
"""Regression controls for the REPORTER adapter contract (runner-graded reporters).

R1  a reporter that prints a WRONG result and exits 0 must go red (determinate SUITE, exit 1), with a positive control.
R2  the real erc8275 mutation-coverage check, with its guard forced off (every vector reports __MUTATION_SURVIVED__)
    and its checker correctly REPINNED, must go red: a valid pin does not waive grading.
R3  a reporter that omits a result on a suite listed in conformance/uncovered.json must still fail. It must never be
    rewritten to NOT RUN, which is what happens to NOT COVERED on a declared suite.
Plus the edge cases of the contract: missing / extra / empty / invalid / duplicate-key / NaN reports, the {"results": map}
envelope, invalid and empty corpora, the reserved "results" name, nonzero reporter exits, must_not_equal presence,
int-vs-float exactness, stderr kept out of parsing, and a missing or unknown adapter.contract.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import run_conformance as runner

REPO = pathlib.Path(__file__).resolve().parent.parent


def _cmd(script: pathlib.Path) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([sys.executable, str(script)])
    return " ".join(shlex.quote(p) for p in (sys.executable, str(script)))


def make_suite(root: pathlib.Path, name: str, vectors, stdout: str = "", stderr: str = "", code: int = 0,
               contract="reporter", raw_vectors: str | None = None) -> pathlib.Path:
    d = root / name
    d.mkdir()
    script = d / "adapter.py"
    script.write_text(
        "import sys\nsys.stdin.read()\n"
        f"sys.stdout.write({stdout!r})\nsys.stderr.write({stderr!r})\nraise SystemExit({code})\n",
        encoding="utf-8", newline="\n")
    vf = d / "vectors.json"
    vf.write_text(raw_vectors if raw_vectors is not None else json.dumps({"vectors": vectors}), encoding="utf-8", newline="\n")
    adapter = {"kind": "stdio", "cmd": _cmd(script)}
    if contract is not None:
        adapter["contract"] = contract
    (d / "suite.json").write_text(json.dumps({"vectors": {"path": "vectors.json"}, "adapter": adapter}), encoding="utf-8")
    return d


V2 = [{"name": "a", "expected": 1}, {"name": "b", "expected": {"x": [1, 2]}}]
GOOD = json.dumps({"a": 1, "b": {"x": [1, 2]}})


class Reporter(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def one(self, *a, **k):
        [r] = runner.run_suite(make_suite(self.root, f"s{len(list(self.root.iterdir()))}", *a, **k))
        return r

    # R1
    def test_r1_positive_control_passes(self):
        r = self.one(V2, GOOD)
        self.assertTrue(r.ok, r.detail)

    def test_r1_wrong_result_with_exit_0_is_determinate_refutation(self):
        r = self.one(V2, json.dumps({"a": 2, "b": {"x": [1, 2]}}))
        self.assertEqual((r.ok, r.kind), (False, "SUITE"), r.detail)
        self.assertEqual(runner.exit_code_for_failures([r]), 1)

    def test_key_order_is_irrelevant_array_order_is_not(self):
        self.assertTrue(self.one(V2, '{"b": {"x": [1, 2]}, "a": 1}').ok)
        self.assertEqual(self.one(V2, json.dumps({"a": 1, "b": {"x": [2, 1]}})).kind, "SUITE")

    def test_int_and_float_are_not_the_same_value(self):
        self.assertEqual(self.one([{"name": "a", "expected": 1}], '{"a": 1.0}').kind, "SUITE")

    def test_results_envelope_is_accepted(self):
        self.assertTrue(self.one(V2, json.dumps({"results": json.loads(GOOD)})).ok)

    def test_stderr_diagnostics_are_not_parsed(self):
        self.assertTrue(self.one(V2, GOOD, stderr="progress: 50%\nnot json {{{\n").ok)

    # missing / extra / protocol faults -> REPORT_CONTRACT (exit 2), never PASS
    def test_missing_result(self):
        r = self.one(V2, '{"a": 1}')
        self.assertEqual(r.kind, "REPORT_CONTRACT")
        self.assertIn("MISSING_RESULT", r.detail)
        self.assertEqual(runner.exit_code_for_failures([r]), 2)

    def test_missing_plus_a_witnessed_mismatch_is_still_determinate(self):
        r = self.one(V2, '{"a": 3}')
        self.assertEqual(r.kind, "SUITE")
        self.assertIn("MISSING_RESULT", r.detail)

    def test_extra_result(self):
        r = self.one(V2, json.dumps({**json.loads(GOOD), "zzz": 0}))
        self.assertEqual(r.kind, "REPORT_CONTRACT")
        self.assertIn("EXTRA_RESULT", r.detail)

    def test_null_is_a_value_and_absence_is_not_null(self):
        self.assertTrue(self.one([{"name": "a", "expected": None}], '{"a": null}').ok)
        self.assertEqual(self.one([{"name": "a", "expected": None}], "{}").kind, "REPORT_CONTRACT")

    def test_empty_report(self):
        r = self.one(V2, "")
        self.assertEqual(r.kind, "REPORT_CONTRACT")
        self.assertIn("EMPTY_REPORT", r.detail)

    def test_invalid_reports(self):
        for bad in ("not json", GOOD + GOOD, "[1, 2]", '{"a": 1, "a": 1, "b": {"x": [1, 2]}}',
                    '{"a": NaN, "b": {"x": [1, 2]}}', '{"results": [1]}'):
            with self.subTest(bad=bad[:30]):
                r = self.one(V2, bad)
                self.assertEqual(r.kind, "REPORT_CONTRACT", r.detail)
                self.assertIn("INVALID_REPORT", r.detail)

    def test_nonzero_reporter_exit_is_not_a_self_graded_refutation(self):
        r = self.one(V2, GOOD, code=1)
        self.assertEqual(r.kind, "REPORT_CONTRACT")
        self.assertIn("ADAPTER_FAILED", r.detail)
        self.assertEqual(self.one(V2, GOOD, code=2).kind, "REPORT_CONTRACT")

    # corpus
    def test_invalid_corpora(self):
        cases = {
            "EMPTY_CORPUS": json.dumps({"vectors": []}),
            "duplicate vector name": json.dumps({"vectors": [{"name": "a", "expected": 1}, {"name": "a", "expected": 1}]}),
            "reserved": json.dumps({"vectors": [{"name": "results", "expected": 1}]}),
            "declares no expected": json.dumps({"vectors": [{"name": "a"}]}),
            "duplicate member": '{"vectors": [{"name": "a", "expected": 1, "expected": 2}]}',
            "expects the value it forbids": json.dumps({"vectors": [{"name": "a", "expected": None, "must_not_equal": None}]}),
        }
        for why, raw in cases.items():
            with self.subTest(why=why):
                r = self.one(None, '{"a": 1}', raw_vectors=raw)
                self.assertEqual(r.kind, "REPORT_CONTRACT", r.detail)
                self.assertIn(why, r.detail)

    def test_must_not_equal_uses_presence_not_truthiness(self):
        # a forbidden null is a real constraint; a different expected value still passes
        self.assertTrue(self.one([{"name": "a", "expected": 1, "must_not_equal": None}], '{"a": 1}').ok)
        self.assertEqual(self.one([{"name": "a", "expected": 1, "must_not_equal": None}], '{"a": null}').kind, "SUITE")

    # the contract discriminator
    def test_missing_or_unknown_contract_is_not_covered(self):
        for c in (None, "grader", ""):
            with self.subTest(contract=c):
                r = self.one(V2, GOOD, contract=c)
                self.assertEqual(r.kind, "NOT COVERED")

    def test_self_grading_keeps_exit_status_semantics(self):
        self.assertTrue(self.one(V2, "whatever it prints", contract="self_grading").ok)
        self.assertEqual(self.one(V2, "", code=1, contract="self_grading").kind, "SUITE")


class R2ErcMutationSurvival(unittest.TestCase):
    """R2 on the real suite: forced mutation survival, checker correctly repinned, must be refuted."""
    SRC = REPO / "conformance" / "erc8275-win-rate-bps-v0"

    def _copy(self, tmp: pathlib.Path, force_survival: bool) -> pathlib.Path:
        d = tmp / "erc8275-win-rate-bps-v0"
        shutil.copytree(self.SRC, d)
        if force_survival:
            g = d / "gate.py"
            src = g.read_text(encoding="utf-8")
            self.assertIn("        guards_hold = (\n", src)
            g.write_text(src.replace("        guards_hold = (\n", "        guards_hold = False and (\n", 1), encoding="utf-8")
            m = json.loads((d / "suite.json").read_text(encoding="utf-8"))
            m["checker"]["sha256"] = hashlib.sha256(g.read_bytes()).hexdigest()     # a valid, updated pin
            (d / "suite.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
        return d

    def test_unmodified_suite_passes_both_checks(self):
        with tempfile.TemporaryDirectory() as t:
            rs = {r.name.split("/")[-1]: r for r in runner.run_suite(self._copy(pathlib.Path(t), False))}
            self.assertTrue(rs["conformance"].ok, rs["conformance"].detail)
            self.assertTrue(rs["mutation-coverage"].ok, rs["mutation-coverage"].detail)

    def test_forced_survival_with_valid_pin_is_refuted(self):
        with tempfile.TemporaryDirectory() as t:
            rs = {r.name.split("/")[-1]: r for r in runner.run_suite(self._copy(pathlib.Path(t), True))}
            self.assertTrue(rs["conformance"].ok, rs["conformance"].detail)
            mc = rs["mutation-coverage"]
            self.assertEqual((mc.ok, mc.kind), (False, "SUITE"), mc.detail)
            self.assertIn("__MUTATION_SURVIVED__", mc.detail)


class R3DeclaredUncoveredOmission(unittest.TestCase):
    """R3: the uncovered.json pass rewrites NOT COVERED on a declared suite to NOT RUN (build-silent). A reporter that
    omits a result on such a suite must still take the run red and stay visible by cause."""

    def test_declared_suite_reporter_omission_still_fails(self):
        with tempfile.TemporaryDirectory() as t:
            conf = pathlib.Path(t) / "conformance"
            conf.mkdir()
            make_suite(conf, "listed-reporter", V2, '{"a": 1}')
            (conf / "uncovered.json").write_text(json.dumps({
                "uncovered": [{"suite": "listed-reporter", "reason": "R3 control"}],
                "undeclared_vectors": [], "requires_live": []}), encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(runner, "CONFORMANCE", conf), contextlib.redirect_stdout(out):
                code = runner.main()
            text = out.getvalue()
            self.assertNotEqual(code, 0, text)
            self.assertNotIn("NOT RUN      listed-reporter", text)
            self.assertIn("REPORT CONTRACT", text)

    def test_report_contract_is_listed_in_not_green_by_cause(self):
        with tempfile.TemporaryDirectory() as t:
            conf = pathlib.Path(t) / "conformance"
            conf.mkdir()
            make_suite(conf, "r", V2, '{"a": 1}')
            (conf / "uncovered.json").write_text('{"uncovered":[],"undeclared_vectors":[],"requires_live":[]}', encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(runner, "CONFORMANCE", conf), contextlib.redirect_stdout(out):
                code = runner.main()
            text = out.getvalue()
            self.assertEqual(code, 2, text)
            by_cause = text.split("not green, by cause:", 1)[1]
            self.assertIn("reporter did not complete the reporter contract", by_cause)
            self.assertIn("MISSING_RESULT", by_cause)


if __name__ == "__main__":
    unittest.main(verbosity=2)
