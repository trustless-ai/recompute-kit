#!/usr/bin/env python3
"""Runtime dependencies are a precondition checked before execution, never a stderr classification after it.

The failure this guards (#68): ENVIRONMENT_FAILURE_SIGNATURES matched bun's wording for a missing package, bun's wording
floated with bun-version: latest, and an induced infrastructure break read as a refuted vector. A declared dependency
that is missing must be RUNNER without the adapter ever running, and an import the manifest does not declare must be
NOT COVERED, so the declaration list cannot silently exempt whatever is new.
"""

from __future__ import annotations

import json
import pathlib
import shlex
import sys
import tempfile
import unittest
from unittest import mock

import run_conformance as runner


def suite_with(files: dict, runtime=None, cmd=None) -> tuple[tempfile.TemporaryDirectory, pathlib.Path, dict]:
    tmp = tempfile.TemporaryDirectory()
    d = pathlib.Path(tmp.name) / "s"
    d.mkdir()
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8")
    m = {"adapter": {"kind": "stdio", "contract": "self_grading",
                     "cmd": cmd or f"{shlex.quote(sys.executable)} adapter.py"}}
    if runtime is not None:
        m["runtime"] = runtime
    return tmp, d, m


ADAPTER = "raise SystemExit(0)\n"


class RuntimePreconditionTests(unittest.TestCase):
    def run_one(self, d, m):
        with mock.patch.object(runner.subprocess, "run", side_effect=AssertionError("adapter must not run")):
            return runner._run_one(d, m, "s")

    def test_undeclared_node_import_is_not_covered(self):
        tmp, d, m = suite_with({"adapter.py": ADAPTER, "gate.ts": 'import { ethers } from "ethers";\n'})
        with tmp:
            r = self.run_one(d, m)
        self.assertEqual("NOT COVERED", r.kind)
        self.assertIn("ethers", r.detail)

    def test_scoped_subpath_import_names_the_package(self):
        tmp, d, m = suite_with({"adapter.py": ADAPTER, "gate.mjs": "import { sha256 } from '@noble/hashes/sha2';\n"})
        with tmp:
            r = self.run_one(d, m)
        self.assertEqual("NOT COVERED", r.kind)
        self.assertIn("@noble/hashes", r.detail)

    def test_builtins_relative_and_comments_are_not_dependencies(self):
        src = ('import fs from "node:fs";\nimport { x } from "./local.ts";\n'
               '// import nope from "commented-out";\n/* require("also-not") */\n')
        tmp, d, m = suite_with({"adapter.py": "import json, sys\nimport local_helper\n", "local_helper.py": "",
                                "gate.ts": src})
        with tmp:
            self.assertIsNone(runner._check_runtime(d, m, m["adapter"]["cmd"]))

    def test_undeclared_python_import_is_not_covered(self):
        tmp, d, m = suite_with({"adapter.py": "import rfc8785_not_installed_xyz\n"})
        with tmp:
            r = self.run_one(d, m)
        self.assertEqual("NOT COVERED", r.kind)
        self.assertIn("rfc8785_not_installed_xyz", r.detail)

    def test_declared_but_missing_python_module_is_runner_before_execution(self):
        tmp, d, m = suite_with({"adapter.py": "import rfc8785_not_installed_xyz\n"},
                               runtime={"python_modules": ["rfc8785_not_installed_xyz"]})
        with tmp:
            r = self.run_one(d, m)
        self.assertEqual("RUNNER", r.kind)
        self.assertIn("precondition", r.detail)

    def test_declared_but_unresolvable_node_package_is_runner(self):
        tmp, d, m = suite_with({"adapter.py": ADAPTER, "gate.ts": 'import { ethers } from "ethers";\n'},
                               runtime={"node_packages": ["ethers"]})
        with tmp, mock.patch.object(runner, "_resolves_node_package", return_value=False):
            r = self.run_one(d, m)
        self.assertEqual("RUNNER", r.kind)
        self.assertIn("node package ethers", r.detail)

    def test_missing_interpreter_is_runner_even_when_undeclared(self):
        tmp, d, m = suite_with({"adapter.py": ADAPTER}, cmd="definitely-not-a-real-interpreter-xyz gate.ts")
        with tmp:
            r = self.run_one(d, m)
        self.assertEqual("RUNNER", r.kind)
        self.assertIn("definitely-not-a-real-interpreter-xyz", r.detail)

    def test_node_resolution_walks_up_from_the_suite(self):
        tmp, d, m = suite_with({"adapter.py": ADAPTER})
        with tmp:
            pkg = d.parent / "node_modules" / "ethers"
            pkg.mkdir(parents=True)
            (pkg / "package.json").write_text("{}")
            with mock.patch.object(runner, "ROOT", d.parent):
                self.assertTrue(runner._resolves_node_package(d, "ethers"))
                self.assertFalse(runner._resolves_node_package(d, "absent"))

    def test_malformed_runtime_is_not_covered(self):
        for bad in ({"commands": "bun"}, {"packages": ["x"]}, ["bun"], {"commands": [""]}):
            tmp, d, m = suite_with({"adapter.py": ADAPTER}, runtime=bad)
            with tmp:
                self.assertEqual("NOT COVERED", self.run_one(d, m).kind, bad)

    def test_every_repo_suite_declares_what_it_imports(self):
        # The repository itself must satisfy the rule it enforces: no suite may import an undeclared dependency.
        for manifest in sorted(runner.CONFORMANCE.glob("*/suite.json")):
            d, m = manifest.parent, json.loads(manifest.read_text())
            rt = m.get("runtime", {})
            self.assertFalse(runner._imported_node_packages(d) - set(rt.get("node_packages", [])), d.name)
            self.assertFalse(runner._imported_python_modules(d) - set(rt.get("python_modules", [])), d.name)


class RuntimePreconditionCornerTests(unittest.TestCase):
    def test_bare_node_core_modules_are_not_packages(self):
        src = 'import fs from "fs";\nimport { join } from "path";\nconst c = require("crypto");\nimport { readFile } from "fs/promises";\n'
        tmp, d, m = suite_with({"adapter.py": ADAPTER, "gate.mjs": src}, runtime={})
        with tmp:
            self.assertEqual(set(), runner._imported_node_packages(d))

    def test_optional_python_import_with_fallback_is_neither_required_nor_flagged(self):
        src = ("try:\n    import rfc8785\nexcept ImportError:\n    rfc8785 = None\n"
               "try:\n    from nacl.signing import VerifyKey\nexcept (ImportError, ModuleNotFoundError):\n    VerifyKey = None\n")
        tmp, d, m = suite_with({"adapter.py": ADAPTER + src}, runtime={})
        with tmp:
            self.assertEqual(set(), runner._imported_python_modules(d))

    def test_required_import_next_to_an_optional_one_is_still_flagged(self):
        src = "import requests\ntry:\n    import rfc8785\nexcept ImportError:\n    rfc8785 = None\n"
        tmp, d, m = suite_with({"adapter.py": ADAPTER + src}, runtime={})
        with tmp:
            self.assertEqual({"requests"}, runner._imported_python_modules(d))


if __name__ == "__main__":
    unittest.main(verbosity=2)
