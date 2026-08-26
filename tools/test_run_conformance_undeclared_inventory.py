"""Regression: the undeclared-JSON inventory must not misclassify a manifest-declared
spec.path as an unrun vector file, while still catching a genuinely undeclared .json.

Both sides matter (the no-silent-skips invariant):
  - manifest vectors.path + JSON spec.path -> spec is NOT reported undeclared;
  - an additional unrelated .json beside them -> STILL reported undeclared.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_conformance as runner  # noqa: E402


def _make_suite(tmp: str, manifest: dict, files: dict[str, str]) -> pathlib.Path:
    d = pathlib.Path(tmp) / "suite-x"
    d.mkdir()
    (d / "suite.json").write_text(json.dumps(manifest))
    for name, content in files.items():
        (d / name).write_text(content)
    return d


class UndeclaredInventoryTests(unittest.TestCase):
    MANIFEST = {"vectors": {"path": "x.vectors.json"},
                "spec": {"path": "x.schema.json", "sha256": "deadbeef"}}

    def test_declared_spec_path_is_not_reported_undeclared(self):
        # vectors.path + spec.path both declared, both present -> nothing undeclared
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_suite(tmp, self.MANIFEST,
                            {"x.vectors.json": "{}", "x.schema.json": "{}"})
            self.assertEqual(runner.undeclared_json_files(d), [])

    def test_unrelated_json_beside_spec_is_still_reported(self):
        # add an unrelated .json -> spec stays declared, the stray file is caught
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_suite(tmp, self.MANIFEST,
                            {"x.vectors.json": "{}", "x.schema.json": "{}", "stray.json": "{}"})
            self.assertEqual(runner.undeclared_json_files(d), ["stray.json"])

    def test_spec_only_manifest_still_covers_its_spec(self):
        # a manifest that declares only a spec (no vectors) still counts spec as declared
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_suite(tmp, {"spec": {"path": "x.schema.json", "sha256": "x"}},
                            {"x.schema.json": "{}"})
            self.assertEqual(runner.undeclared_json_files(d), [])

    def test_no_manifest_reports_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp) / "no-suite"
            d.mkdir()
            (d / "loose.json").write_text("{}")
            self.assertEqual(runner.undeclared_json_files(d), [])


if __name__ == "__main__":
    unittest.main()
