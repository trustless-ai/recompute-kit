"""scan-subject-binding-v0: a case that was never graded is not a refuted case (#79).

Controls (Pavlo's boundary on #79):
1. missing expectation -> exit 2 (UNVERIFIABLE), never SUITE;
2. a genuine mismatch -> exit 1 (SUITE);
3. mixed: a mismatch plus an ungradable case -> exit 1, both named in the output;
4. removing the guard restores the old wrong classification (SUITE from a KeyError);
5. a c0 case whose nonempty expect lacks its answer fields -> exit 2, not a KeyError (Pavlo, #82);
6. a non-c0 case whose nonempty expect names no graded field -> exit 2, not counted as reproduced (Pavlo, #82).
Runs on a disposable copy of the suite; the real corpus is untouched.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_conformance as runner

SUITE = Path(__file__).resolve().parent.parent / "conformance" / "scan-subject-binding-v0"
GUARD = "if not gradable(name, c):"


class UngradableCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(SUITE, self.tmp / "s")
        self.dir = self.tmp / "s"
        self.vectors = json.loads((SUITE / "vectors.json").read_text())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _probe(self, *, drop_expect=True, break_one=False):
        v = copy.deepcopy(self.vectors)
        name = next(n for n in sorted(v["cases"]) if not n.startswith("c0"))
        if drop_expect:
            probe = copy.deepcopy(v["cases"][name])
            del probe["expect"]
            v["cases"][name + "__probe_no_expect"] = probe
        if break_one:
            e = v["cases"][name]["expect"]
            e["subject_bound_check"] = "NOT_A_VERDICT"
        (self.dir / "vectors.json").write_text(json.dumps(v))

    def _run(self):
        p = subprocess.run([sys.executable, "scan_check.py", "vectors.json"], cwd=self.dir,
                           capture_output=True, text=True, timeout=120)
        out = p.stdout + p.stderr
        kind = None if p.returncode == 0 else runner.classify_process_failure(p.returncode, out, "scan_check.py").kind
        return p.returncode, kind, p.stdout, p.stderr

    def test_1_missing_expectation_is_unverifiable(self):
        self._probe()
        rc, kind, out, err = self._run()
        self.assertEqual((rc, kind), (2, "UNVERIFIABLE"))
        doc = json.loads(out)
        self.assertEqual(len(doc["ungradable"]), 1)
        self.assertEqual(doc["total"] + len(doc["ungradable"]), doc["admitted"])
        self.assertEqual(doc["reproduced"], doc["total"])

    def test_2_genuine_mismatch_is_refutation(self):
        self._probe(drop_expect=False, break_one=True)
        rc, kind, _, _ = self._run()
        self.assertEqual((rc, kind), (1, "SUITE"))

    def test_3_mixed_keeps_both_refutation_wins(self):
        self._probe(break_one=True)
        rc, kind, out, err = self._run()
        self.assertEqual((rc, kind), (1, "SUITE"))
        doc = json.loads(out)
        self.assertEqual(len(doc["ungradable"]), 1)
        self.assertLess(doc["reproduced"], doc["total"])
        self.assertIn("no usable expectation to grade against", err)

    def test_4_guard_is_load_bearing(self):
        src = (self.dir / "scan_check.py").read_text()
        self.assertEqual(src.count(GUARD), 1)
        (self.dir / "scan_check.py").write_text(src.replace(GUARD, "if False:"))
        self._probe()
        rc, kind, _, err = self._run()
        self.assertEqual((rc, kind), (1, "SUITE"))
        self.assertIn("KeyError", err)

    def _probe_expect(self, *, c0, expect):
        v = copy.deepcopy(self.vectors)
        name = next(n for n in sorted(v["cases"]) if n.startswith("c0") == c0)
        probe = copy.deepcopy(v["cases"][name])
        probe["expect"] = expect
        v["cases"][name + "__probe"] = probe
        (self.dir / "vectors.json").write_text(json.dumps(v))
        return name + "__probe"

    def _assert_ungradable(self, probe):
        rc, kind, out, err = self._run()
        self.assertEqual((rc, kind), (2, "UNVERIFIABLE"), err)
        doc = json.loads(out)
        self.assertEqual(doc["ungradable"], [probe])
        self.assertEqual(doc["reproduced"], doc["total"])
        self.assertEqual(doc["total"] + 1, doc["admitted"])
        self.assertNotIn("KeyError", err)

    def test_5_c0_expect_without_answers_is_unverifiable(self):
        self._assert_ungradable(self._probe_expect(c0=True, expect={"signatures": "valid"}))

    def test_6_metadata_only_expect_is_not_reproduced(self):
        self._assert_ungradable(self._probe_expect(c0=False, expect={"reason": "metadata only"}))

    def test_real_corpus_still_passes(self):
        rc, _, out, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["ungradable"], [])


if __name__ == "__main__":
    unittest.main()
