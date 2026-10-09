"""Regression: a declared checker / mutation_checker / dependencies sha256 pin is enforced like
vectors.sha256 and spec.sha256. Before this, editing mutation_check.py without repinning still passed.

  - control: every declared pin matches -> the suite runs and passes;
  - each of checker, mutation_checker and a dependency edited after pinning -> DRIFT;
  - a pinned file that is missing -> NOT COVERED, never a silent skip;
  - a manifest that pins none of them is unchanged;
  - a pin that is declared but malformed (bare string, empty/non-hex sha256, typo'd key) -> NOT COVERED, not skipped.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_conformance as runner  # noqa: E402


def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _suite(tmp: str, pin_checker=True, pin_mutation=True, pin_dep=True) -> pathlib.Path:
    d = pathlib.Path(tmp) / "suite-x"
    d.mkdir()
    files = {"check.py": b"import sys\nsys.stdin.read()\n", "mutation.py": b"print('m')\n", "dep.py": b"print('d')\n", "vectors.json": b"[]"}
    for n, b in files.items():
        (d / n).write_bytes(b)
    m = {"vectors": {"path": "vectors.json", "sha256": _h(files["vectors.json"])}, "adapter": {"kind": "stdio", "cmd": "python3 check.py", "contract": "self_grading"}}
    if pin_checker:
        m["checker"] = {"path": "check.py", "sha256": _h(files["check.py"])}
    if pin_mutation:
        m["mutation_checker"] = {"path": "mutation.py", "sha256": _h(files["mutation.py"])}
    if pin_dep:
        m["dependencies"] = [{"path": "dep.py", "sha256": _h(files["dep.py"])}]
    (d / "suite.json").write_text(json.dumps(m))
    return d


class CheckerPinTests(unittest.TestCase):
    def _run(self, d):
        return runner.run_suite(d)[0]

    def test_control_matching_pins_pass(self):
        with tempfile.TemporaryDirectory() as t:
            r = self._run(_suite(t))
            self.assertTrue(r.ok, (r.kind, r.detail))

    def test_edited_files_after_pinning_are_drift(self):
        for fname, key in (("check.py", "checker"), ("mutation.py", "mutation_checker"), ("dep.py", "dependencies")):
            with self.subTest(fname):
                with tempfile.TemporaryDirectory() as t:
                    d = _suite(t)
                    (d / fname).write_bytes((d / fname).read_bytes() + b"# edited\n")
                    r = self._run(d)
                    self.assertFalse(r.ok)
                    self.assertEqual(r.kind, "DRIFT")
                    self.assertIn(key, r.detail)

    def test_missing_pinned_file_is_not_covered(self):
        with tempfile.TemporaryDirectory() as t:
            d = _suite(t)
            (d / "mutation.py").unlink()
            r = self._run(d)
            self.assertFalse(r.ok)
            self.assertEqual(r.kind, "NOT COVERED")

    def test_unpinned_manifest_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            d = _suite(t, pin_checker=False, pin_mutation=False, pin_dep=False)
            (d / "check.py").write_bytes(b"import sys\nsys.stdin.read()\n# edited\n")
            self.assertTrue(self._run(d).ok)

    def test_declared_but_malformed_pins_are_not_covered(self):
        """Zexo (damon/receiptos, 2026-09-25): a declared pin that cannot be enforced was skipped, so it read as enforced."""
        good = _h(b"import sys\nsys.stdin.read()\n")
        cases = {
            "bare string": "check.py",
            "empty sha256": {"path": "check.py", "sha256": ""},
            "typo sha265": {"path": "check.py", "sha265": good},
            "uppercase hex": {"path": "check.py", "sha256": good.upper()},
            "short hex": {"path": "check.py", "sha256": good[:63]},
            "empty path": {"path": "", "sha256": good},
            "null": None,
        }
        for name, entry in cases.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as t:
                    d = _suite(t, pin_checker=False)
                    m = json.loads((d / "suite.json").read_text()); m["checker"] = entry
                    (d / "suite.json").write_text(json.dumps(m))
                    r = self._run(d)
                    self.assertFalse(r.ok)
                    self.assertEqual(r.kind, "NOT COVERED", r.detail)
                    self.assertIn("malformed", r.detail)

    def test_dependencies_not_a_list_is_not_covered(self):
        with tempfile.TemporaryDirectory() as t:
            d = _suite(t, pin_dep=False)
            m = json.loads((d / "suite.json").read_text()); m["dependencies"] = {"path": "dep.py", "sha256": "0" * 64}
            (d / "suite.json").write_text(json.dumps(m))
            r = self._run(d)
            self.assertEqual((r.ok, r.kind), (False, "NOT COVERED"), r.detail)

    def test_annotation_keys_on_a_wellformed_pin_are_allowed(self):
        with tempfile.TemporaryDirectory() as t:
            d = _suite(t)
            m = json.loads((d / "suite.json").read_text()); m["checker"]["note"] = "reused unmodified from another suite"
            (d / "suite.json").write_text(json.dumps(m))
            r = self._run(d)
            self.assertTrue(r.ok, (r.kind, r.detail))


if __name__ == "__main__":
    unittest.main()
