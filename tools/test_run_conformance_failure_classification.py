#!/usr/bin/env python3
"""Regression tests for conformance-runner failure attribution and precedence."""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import run_conformance as runner


def command_for(script: pathlib.Path) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([sys.executable, str(script)])
    import shlex
    return " ".join(shlex.quote(part) for part in (sys.executable, str(script)))


def add_failing_suite(root: pathlib.Path, name: str, output: str) -> None:
    suite = root / name
    suite.mkdir()
    adapter = suite / "adapter.py"
    adapter.write_text(
        "import sys\n"
        f"print({output!r})\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
        newline="\n",
    )
    vectors = suite / "vectors.json"
    vectors.write_text("{}\n", encoding="utf-8", newline="\n")
    manifest = {
        "profile": name,
        "vectors": {"path": vectors.name},
        "adapter": {"kind": "stdio", "cmd": command_for(adapter)},
    }
    (suite / "suite.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_temporary_repository(suites: list[tuple[str, str]]) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as temporary:
        conformance = pathlib.Path(temporary) / "conformance"
        conformance.mkdir()
        (conformance / "uncovered.json").write_text(
            '{"uncovered":[],"undeclared_vectors":[],"requires_live":[]}\n',
            encoding="utf-8",
            newline="\n",
        )
        for name, output in suites:
            add_failing_suite(conformance, name, output)
        captured = io.StringIO()
        with mock.patch.object(runner, "CONFORMANCE", conformance), contextlib.redirect_stdout(captured):
            return runner.main(), captured.getvalue()


class ProcessFailureClassificationTests(unittest.TestCase):
    def assert_runner(self, output: str) -> None:
        failure = runner.classify_process_failure(1, output, "adapter command")
        self.assertEqual("RUNNER", failure.kind)
        self.assertIn("environment, not evidence", failure.detail)

    def test_bun_dependency_resolution_is_runner(self) -> None:
        self.assert_runner("Unexpected while resolving package '@noble/hashes/crypto'")

    def test_node_and_bun_missing_dependency_forms_remain_runner(self) -> None:
        for output in (
            "Error: Cannot find module 'ethers'",
            "error: Cannot find package '@noble/hashes' from '/work/gate.ts'",
            "ENOENT: no such file or directory, open 'node_modules/x'",
        ):
            with self.subTest(output=output):
                self.assert_runner(output)

    def test_python_import_forms_remain_runner(self) -> None:
        for output in (
            "ModuleNotFoundError: No module named 'cryptography'",
            "ImportError: cannot import name 'Verifier' from 'package'",
        ):
            with self.subTest(output=output):
                self.assert_runner(output)

    def test_missing_interpreter_exit_is_runner(self) -> None:
        failure = runner.classify_process_failure(127, "", "missing-interpreter adapter.py")
        self.assertEqual("RUNNER", failure.kind)

    def test_semantic_failure_is_suite(self) -> None:
        failure = runner.classify_process_failure(
            1,
            "assertion mismatch: expected digest 00, reproduced digest ff",
            "adapter command",
        )
        self.assertEqual("SUITE", failure.kind)

    def test_generic_words_do_not_become_runner(self) -> None:
        failure = runner.classify_process_failure(
            1,
            "Unexpected: package assertion failed for vector alpha; error status differs",
            "adapter command",
        )
        self.assertEqual("SUITE", failure.kind)

    def test_timeout_remains_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = pathlib.Path(temporary)
            manifest = {"adapter": {"kind": "stdio", "cmd": "slow adapter"}}
            with mock.patch.object(
                runner.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("slow adapter", 300),
            ):
                result = runner._run_one(suite, manifest, "timeout")
        self.assertEqual("RUNNER", result.kind)
        self.assertIn("timed out", result.detail)

    def test_digest_drift_remains_determinate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = pathlib.Path(temporary)
            (suite / "vectors.json").write_text("{}\n", encoding="utf-8", newline="\n")
            manifest = {
                "vectors": {"path": "vectors.json", "sha256": "0" * 64},
                "adapter": {"kind": "stdio", "cmd": "unused adapter"},
            }
            result = runner._run_one(suite, manifest, "drift")
        self.assertEqual("DRIFT", result.kind)
        self.assertEqual(1, runner.exit_code_for_failures([result]))


class FinalExitSemanticsTests(unittest.TestCase):
    def test_environment_only_repository_exits_two(self) -> None:
        code, output = run_temporary_repository([
            ("bun-resolution", "Unexpected while resolving package '@noble/hashes/crypto'"),
        ])
        self.assertEqual(2, code)
        self.assertIn("runner could not execute it (environment, not evidence)", output)
        self.assertNotIn("suite failed (a vector did not reproduce)", output)

    def test_real_semantic_refutation_exits_one(self) -> None:
        code, output = run_temporary_repository([
            ("semantic-refutation", "vector mismatch: expected 00, got ff"),
        ])
        self.assertEqual(1, code)
        self.assertIn("suite failed (a vector did not reproduce)", output)
        self.assertNotIn("runner could not execute it (environment, not evidence)", output)

    def test_mixed_state_exits_one_and_reports_both_causes(self) -> None:
        code, output = run_temporary_repository([
            ("dependency-break", "Unexpected while resolving package '@noble/hashes/crypto'"),
            ("semantic-refutation", "vector mismatch: expected 00, got ff"),
        ])
        self.assertEqual(1, code)
        self.assertIn("suite failed (a vector did not reproduce)", output)
        self.assertIn("runner could not execute it (environment, not evidence)", output)

    def test_exit_precedence_helper_includes_drift(self) -> None:
        runner_failure = runner.Result("environment", False, "RUNNER", "missing dependency")
        suite_failure = runner.Result("semantic", False, "SUITE", "mismatch")
        drift_failure = runner.Result("pins", False, "DRIFT", "digest mismatch")
        self.assertEqual(0, runner.exit_code_for_failures([]))
        self.assertEqual(2, runner.exit_code_for_failures([runner_failure]))
        self.assertEqual(1, runner.exit_code_for_failures([suite_failure, runner_failure]))
        self.assertEqual(1, runner.exit_code_for_failures([drift_failure]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
