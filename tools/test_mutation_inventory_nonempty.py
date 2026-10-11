"""Zero mutation/fault inventories are unverifiable, never successful coverage.

Exercise the real harnesses in a disposable copy. Repin intentional source probes
so ZERO_MUTANTS cannot be confused with digest drift. CRASH, NOT_APPLIED and
SURVIVED remain distinct from a witnessed KILLED result. No repository bytes are
changed, and copied modules cannot use stale bytecode.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_conformance as runner

ROOT = Path(__file__).resolve().parent.parent
SUITES = (
    "authorized-preimage-schema-v0",
    "consumption-time-state-binding-v0",
    "event-time-concurrency-boundary-v0",
    "permission-consumption-boundary-v0",
    "scan-subject-binding-v0",
)
ENCODE = "encode-json-utf8-lf-v0"


def inventory_node(source, name):
    matches = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} inventory")
    return matches[0]


def set_inventory(source, name, mode, before_index=2):
    node = inventory_node(source, name)
    if mode == "empty":
        setup = f"{name} = []\n"
    else:
        setup = f"{name} = {name}[:1]\n"
        if mode in {"CRASH", "NOT_APPLIED", "SURVIVED"}:
            setup += f"_probe = list({name}[0])\n"
            if mode == "CRASH":
                setup += f"_probe[{before_index + 1}] = '__INVALID_SYNTAX ((('\n"
            elif mode == "NOT_APPLIED":
                setup += f"_probe[{before_index}] = '__NO_SUCH_MUTATION_SITE__'\n"
            else:
                setup += f"_probe[{before_index + 1}] = _probe[{before_index}]\n"
            setup += f"{name} = [tuple(_probe)]\n"
    lines = source.splitlines(keepends=True)
    return "".join(lines[:node.end_lineno]) + setup + "".join(lines[node.end_lineno:])


def without_inventory_guard(source, name):
    main = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    guards = [n for n in main.body if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp)
              and isinstance(n.test.op, ast.Not) and isinstance(n.test.operand, ast.Name)
              and n.test.operand.id == name]
    if len(guards) != 1:
        raise ValueError(f"expected exactly one {name} guard")
    guard = guards[0]
    lines = source.splitlines(keepends=True)
    return "".join(lines[:guard.lineno - 1] + lines[guard.end_lineno:])


class MutationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="nonempty-mutations-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.repo = Path(cls.tmp.name) / "repo"
        shutil.copytree(ROOT, cls.repo, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.pyc"))
        cls.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        cls.flags = ["-B"] + (["-O"] if sys.flags.optimize else [])

    def run_script(self, suite, script="mutation_check.py", *args):
        return subprocess.run([sys.executable, *self.flags, script, *args],
                              cwd=self.repo / "conformance" / suite, env=self.env,
                              input=b"", capture_output=True, timeout=120)

    @contextmanager
    def probe(self, suite, source, script="mutation_check.py"):
        directory = self.repo / "conformance" / suite
        path, manifest = directory / script, directory / "suite.json"
        old_source, old_manifest = path.read_bytes(), manifest.read_bytes()
        try:
            path.write_text(source, encoding="utf-8", newline="\n")
            yield directory
        finally:
            path.write_bytes(old_source)
            manifest.write_bytes(old_manifest)

    def source(self, suite, script="mutation_check.py"):
        return (self.repo / "conformance" / suite / script).read_text(encoding="utf-8")

    def canonical(self, directory, script="mutation_check.py"):
        manifest = json.loads((directory / "suite.json").read_text(encoding="utf-8"))
        if "checks" in manifest:
            check = next(c for c in manifest.pop("checks") if c["name"] == "mutation-coverage")
            manifest.update(check)
        # Use the running interpreter on Windows too; retain the declared pins,
        # vectors and canonical execution/classification path unchanged.
        manifest["adapter"]["cmd"] = f'"{sys.executable}" {" ".join(self.flags)} {script}'
        # These probes exercise self-grading, including under the explicit
        # contract runner in #57. This is a test fixture, not manifest migration.
        manifest["adapter"]["contract"] = "self_grading"
        old = os.environ.get("PYTHONDONTWRITEBYTECODE")
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            return runner._run_one(directory, manifest, directory.name)
        finally:
            if old is None:
                os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
            else:
                os.environ["PYTHONDONTWRITEBYTECODE"] = old

    def assert_counts(self, process, status, total):
        self.assertEqual(process.returncode, 0 if status == "KILLED" else 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(len(report["mutations"]), total)
        self.assertEqual(report["counts"][status], total)
        self.assertTrue(all(n == (total if k == status else 0) for k, n in report["counts"].items()), report)
        self.assertTrue(all(m["status"] == status for m in report["mutations"]), report)
        if status in {"KILLED", "SURVIVED"}:
            self.assertTrue(all(m["controls_preserved"] for m in report["mutations"]), report)
        return report

    def test_nonempty_inventories_kill_with_controls_preserved(self):
        for suite in SUITES:
            with self.subTest(suite=suite):
                directory = self.repo / "conformance" / suite
                manifest = json.loads((directory / "suite.json").read_text(encoding="utf-8"))
                self.assertIsNone(runner._check_declared_pins(directory, manifest))
                total = len(inventory_node(self.source(suite), "MUTANTS").value.elts)
                self.assertGreater(total, 0)
                report = self.assert_counts(self.run_script(suite), "KILLED", total)
                self.assertTrue(report.get("positive_controls", report.get("controls")))
                self.assertTrue(all(report.get("primitive_controls", {}).values()))

    def test_empty_inventory_is_unverifiable_after_repin_not_drift(self):
        for suite in SUITES:
            with self.subTest(suite=suite):
                with self.probe(suite, set_inventory(self.source(suite), "MUTANTS", "empty")) as directory:
                    process = self.run_script(suite)
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertEqual(json.loads(process.stdout), {"status": "ZERO_MUTANTS", "total": 0})
                    stale = self.canonical(directory)
                    self.assertEqual((stale.ok, stale.kind), (False, "DRIFT"), stale.detail)
                    manifest_path = directory / "suite.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["mutation_checker"]["sha256"] = hashlib.sha256((directory / "mutation_check.py").read_bytes()).hexdigest()
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
                    repinned = self.canonical(directory)
                    self.assertEqual((repinned.ok, repinned.kind), (False, "UNVERIFIABLE"), repinned.detail)
                    self.assertIn("ZERO_MUTANTS", repinned.detail)
                    self.assertEqual(runner.exit_code_for_failures([repinned]), 2)

    def test_single_kill_crash_not_applied_and_survived_are_distinct(self):
        for suite in SUITES:
            index = 3 if suite == "event-time-concurrency-boundary-v0" else 2
            for status in ("KILLED", "CRASH", "NOT_APPLIED", "SURVIVED"):
                with self.subTest(suite=suite, status=status):
                    source = set_inventory(self.source(suite), "MUTANTS", status, index)
                    with self.probe(suite, source):
                        self.assert_counts(self.run_script(suite), status, 1)

    def test_removing_guard_reproduces_zero_mutant_false_success(self):
        for suite in SUITES:
            with self.subTest(suite=suite):
                source = set_inventory(without_inventory_guard(self.source(suite), "MUTANTS"), "MUTANTS", "empty")
                with self.probe(suite, source):
                    process = self.run_script(suite)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    report = json.loads(process.stdout)
                    self.assertEqual(report["mutations"], [])
                    self.assertTrue(all(n == 0 for n in report["counts"].values()))

    def test_encode_nonempty_controls_and_single_fault_are_detected(self):
        source = self.source(ENCODE, "gate.py")
        total = len(inventory_node(source, "NEGATIVE_CONTROLS").value.elts)
        self.assertGreater(total, 0)
        process = self.run_script(ENCODE, "gate.py", "--negative-controls")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.count(b"NEGATIVE CONTROL RED "), total)
        with self.probe(ENCODE, set_inventory(source, "NEGATIVE_CONTROLS", "one"), "gate.py"):
            process = self.run_script(ENCODE, "gate.py", "--negative-controls")
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.count(b"NEGATIVE CONTROL RED "), 1)

    def test_encode_empty_controls_fail_both_cli_paths_and_canonical(self):
        source = set_inventory(self.source(ENCODE, "gate.py"), "NEGATIVE_CONTROLS", "empty")
        with self.probe(ENCODE, source, "gate.py") as directory:
            for mode in ("--grade", "--negative-controls"):
                with self.subTest(mode=mode):
                    process = self.run_script(ENCODE, "gate.py", mode)
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertIn(b"ZERO_CONTROLS", process.stderr)
                    self.assertNotIn(b"PASS", process.stdout)
            result = self.canonical(directory, "gate.py")
            self.assertEqual((result.ok, result.kind), (False, "UNVERIFIABLE"), result.detail)
            self.assertIn("ZERO_CONTROLS", result.detail)
            # gate.py is not pinned by the current manifest. Exercise a pin it
            # actually declares; JSON whitespace changes no vector semantics.
            manifest = json.loads((directory / "suite.json").read_text(encoding="utf-8"))
            vector = directory / manifest["vectors"]["path"]
            original = vector.read_bytes()
            try:
                vector.write_bytes(original + b"\n")
                stale = self.canonical(directory, "gate.py")
                self.assertEqual((stale.ok, stale.kind), (False, "DRIFT"), stale.detail)
                self.assertIn(vector.name, stale.detail)
                self.assertNotIn("ZERO_CONTROLS", stale.detail)
            finally:
                vector.write_bytes(original)

    def test_encode_unapplied_fault_or_process_failure_is_not_detection(self):
        source = set_inventory(self.source(ENCODE, "gate.py"), "NEGATIVE_CONTROLS", "one")
        site = '"--negative-control", fault'
        self.assertEqual(source.count(site), 1)
        for replacement, diagnostic in (("", b"negative control stayed green"),
                                         ('"--negative-control", "__UNKNOWN_FAULT__"', b"negative control stayed green"),
                                         ('"--negative-control"', b"adapter exited")):
            with self.subTest(diagnostic=diagnostic):
                with self.probe(ENCODE, source.replace(site, replacement, 1), "gate.py"):
                    process = self.run_script(ENCODE, "gate.py", "--negative-controls")
                    self.assertEqual(process.returncode, 1, process.stderr)
                    self.assertIn(diagnostic, process.stderr)
                    self.assertNotIn(b"NEGATIVE CONTROL RED", process.stdout)

    def test_removing_encode_guard_reproduces_zero_control_false_success(self):
        source = without_inventory_guard(self.source(ENCODE, "gate.py"), "NEGATIVE_CONTROLS")
        with self.probe(ENCODE, set_inventory(source, "NEGATIVE_CONTROLS", "empty"), "gate.py"):
            process = self.run_script(ENCODE, "gate.py", "--negative-controls")
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn(b"PASS negative controls: 0/0", process.stdout)

    def test_no_bytecode_in_disposable_copy(self):
        self.assertEqual(list(self.repo.rglob("*.pyc")), [])


if __name__ == "__main__":
    unittest.main()
