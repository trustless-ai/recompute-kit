"""Issue #79: absent grading information is not a semantic refutation.

Real owners, unique admitted probes, and freshly reloaded/repinned manifests.
Scan's independent owner is covered by PR #82; this suite covers the other
20 declarations / 16 owners. Counts come from the corpus, never adapter output.
The independent completeness test (#78) remains a separate obligation.
"""
from contextlib import contextmanager, redirect_stderr
import copy
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_self_grading_nonempty as fixtures

CHECKS = tuple(sorted(set(fixtures.CHECKS) - {"scan-subject-binding-v0/conformance"}))
Grading = runpy.run_path(str(fixtures.ROOT / "conformance/_self_grading.py"))["Grading"]
SUMMARY = re.compile(r"(?m)^(?:(?:Python|TypeScript) adapter: )?(\d+)/(\d+) (?:cases|vectors)")


class UngradableExpectations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NonemptySelfGradingTests.setUpClass()
        cls.addClassCleanup(fixtures.NonemptySelfGradingTests.doClassCleanups)
        cls.fx = fixtures.NonemptySelfGradingTests()

    @contextmanager
    def corpus(self, check, mode, value=None, repin=True):
        vector, _ = self.fx.paths(check)
        files = [vector, *self.fx.repo.glob("conformance/*/suite.json")]
        original = {p: p.read_bytes() for p in files}
        doc = json.loads(original[vector])
        cases = doc["cases"] if "cases" in doc else doc["vectors"]
        field = next(k for k in ("expect", "expected", "expected_verdict") if k in cases[0])
        if mode not in ("normal", "refuted"):
            extra = copy.deepcopy(cases[0])
            identity = next(k for k in ("name", "case_id", "id") if k in extra)
            extra[identity] += "__issue79_unique_probe"
            if mode in ("missing", "mixed", "mixed-first"):
                del extra[field]
            elif mode == "malformed":
                extra[field] = value
            elif mode == "partial":
                del extra[field][next(iter(extra[field]))]
            elif mode == "bad-field-type":
                key = next(k for k, v in extra[field].items() if isinstance(v, str))
                extra[field][key] = []
            cases.append(extra)
            self.assertEqual(len({c[identity] for c in cases}), len(cases), "probe identities must be unique")
        if mode in ("refuted", "mixed", "mixed-first"):
            expected = cases[0][field]
            if isinstance(expected, dict):
                if check == fixtures.ENCODE:
                    expected["byte_length"] += 1
                else:
                    key = next(k for k, v in expected.items() if isinstance(v, str))
                    expected[key] = "__WRONG_EXPECTED_VALUE__"
            else:
                cases[0][field] = "__WRONG_EXPECTED_VALUE__"
        if mode == "mixed-first":
            cases.insert(0, cases.pop())
        try:
            vector.write_text(json.dumps(doc), encoding="utf-8", newline="\n")
            if repin:
                self.fx.repin(vector)
            yield len(cases), field
        finally:
            for p, data in original.items():
                p.write_bytes(data)

    def classified(self, check, code, kind):
        native = self.fx.native(check)
        self.assertEqual(native.returncode, code, native.stderr.decode())
        self.assertNotIn(b"Traceback", native.stderr)
        # canonical() reloads the manifest after every corpus pin update.
        result = self.fx.canonical(check)
        self.assertEqual(result.ok, code == 0, result)
        if code:
            self.assertEqual(result.kind, kind, result)
            self.assertEqual(fixtures.runner.exit_code_for_failures([result]), code, result)
        return native

    def assert_counts(self, native, reproduced, admitted):
        summaries = SUMMARY.findall(native.stdout.decode())
        self.assertTrue(summaries, native.stdout.decode())
        self.assertTrue(all((int(a), int(b)) == (reproduced, admitted) for a, b in summaries), summaries)

    def test_valid_and_expanded_corpora(self):
        self.assertEqual(len(CHECKS), 20)
        self.assertEqual(len({self.fx.paths(c)[1] for c in CHECKS}), 16)
        for check in CHECKS:
            for mode in ("normal", "extra-valid"):
                with self.subTest(check=check, mode=mode), self.corpus(check, mode) as (n, _):
                    self.assert_counts(self.classified(check, 0, None), n, n)

    def test_missing_expectation_is_not_refuted_or_counted(self):
        for check in CHECKS:
            with self.subTest(check=check), self.corpus(check, "missing") as (n, field):
                p = self.classified(check, 2, "UNVERIFIABLE")
                self.assert_counts(p, n - 1, n)
                self.assertIn(f"missing {field}".encode(), p.stderr)
                self.assertIn(b"refuted=0 ungradable=1", p.stderr)

    def test_malformed_expectation_is_unverifiable(self):
        for check in CHECKS:
            # Empty strings are comparable scalar expectations, not missing values.
            for value in (None, [], {}, False, 0):
                with self.subTest(check=check, value=value), self.corpus(check, "malformed", value) as (n, _):
                    p = self.classified(check, 2, "UNVERIFIABLE")
                    self.assert_counts(p, n - 1, n)
                    self.assertIn(b"UNGRADABLE_CASE", p.stderr)

    def test_required_object_fields_and_types(self):
        for check in CHECKS:
            vector, _ = self.fx.paths(check)
            doc = json.loads(vector.read_bytes())
            c = (doc.get("cases") or doc.get("vectors"))[0]
            field = next(k for k in ("expect", "expected", "expected_verdict") if k in c)
            if not isinstance(c[field], dict):
                continue
            # v1 grades any declared nonempty subset, rather than imposing five fields.
            modes = ("bad-field-type",) if check == "pq-key-binding-v1/cutoff" else ("partial", "bad-field-type")
            for mode in modes:
                with self.subTest(check=check, mode=mode), self.corpus(check, mode):
                    self.classified(check, 2, "UNVERIFIABLE")

    def test_real_refutation_remains_determinate(self):
        for check in CHECKS:
            with self.subTest(check=check), self.corpus(check, "refuted") as (n, _):
                self.assert_counts(self.classified(check, 1, "SUITE"), n - 1, n)

    def test_mixed_preserves_both_causes_and_refutation_precedence(self):
        for check in CHECKS:
            for mode in ("mixed", "mixed-first"):
                with self.subTest(check=check, mode=mode), self.corpus(check, mode) as (n, _):
                    p = self.classified(check, 1, "SUITE")
                    self.assert_counts(p, n - 2, n)
                    self.assertIn(b"UNGRADABLE_CASE", p.stderr)
                    self.assertIn(b"refuted=1 ungradable=1", p.stderr)
                    self.assertTrue(b"BAD" in p.stdout or b"differs from normative expectation" in p.stderr)

    def test_stale_pin_is_separate_drift(self):
        for check in CHECKS:
            with self.subTest(check=check), self.corpus(check, "missing", repin=False):
                r = self.fx.canonical(check)
                self.assertEqual((r.ok, r.kind), (False, "DRIFT"), r)

    def test_runtime_precondition_is_separate_runner_failure(self):
        for check in CHECKS:
            with self.subTest(check=check):
                d, m = self.fx.declaration(check)
                m.setdefault("runtime", {}).setdefault("commands", []).append("__issue79_absent_runtime__")
                r = fixtures.runner._run_one(d, m, check)
                self.assertEqual((r.ok, r.kind), (False, "RUNNER"), r)
                self.assertEqual(fixtures.runner.exit_code_for_failures([r]), 2)

    def test_encode_controls_do_not_use_ungradable_oracle(self):
        with self.corpus(fixtures.ENCODE, "missing"):
            p = self.fx.native(fixtures.ENCODE, controls=True)
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertNotIn(b"NEGATIVE CONTROL RED", p.stdout)
            self.assertNotIn(b"PASS", p.stdout)

    def test_unrecorded_and_duplicate_outcomes_are_not_success(self):
        with redirect_stderr(io.StringIO()) as err:
            g = Grading([{"name": "one"}, {"name": "two"}])
            g.record(0, True)
            self.assertEqual(g.finish(), 2)
            self.assertEqual(g.reproduced, 1)
            self.assertEqual(g.outcomes[1], "ungradable")
            g = Grading([{"name": "one"}])
            g.record(0, True)
            g.record(0, True)
            self.assertEqual(g.finish(), 2)
            self.assertEqual(g.reproduced, 1)
            self.assertIn("GRADING_ACCOUNTING", err.getvalue())

    def test_reference_bookkeeping_has_the_same_boundaries(self):
        helper = (self.fx.repo / "conformance/_self_grading.mjs").as_uri()
        code = f'''import {{ Grading }} from {json.dumps(helper)};
const answers = [];
let g = new Grading([{{name:"valid"}}]); g.record(0, true); answers.push(g.finish());
g = new Grading([{{name:"omitted"}}]); answers.push(g.finish());
g = new Grading([{{name:"duplicate"}}]); g.record(0, true); g.record(0, true); answers.push(g.finish());
g = new Grading([{{name:"refuted"}}, {{name:"unknown"}}]); g.record(0, false); answers.push(g.finish());
console.log(JSON.stringify(answers));'''
        p = subprocess.run(["bun", "-e", code], cwd=self.fx.repo, env=self.fx.env,
                           capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), [0, 2, 2, 1])

    def test_skip_cannot_manufacture_corpus_length_credit(self):
        check = "pq-key-binding-v0/cutoff"
        with self.corpus(check, "extra-valid") as (n, _):
            _, owner = self.fx.paths(check)
            original = owner.read_bytes()
            needle = '        got, exp = admit(bindings, cutoff, c["artifact"]), c["expected"]'
            src = original.decode()
            self.assertEqual(src.count(needle), 1)
            owner.write_text(src.replace(needle, '        if c["name"].endswith("__issue79_unique_probe"):\n            continue\n' + needle), encoding="utf-8")
            try:
                self.fx.repin(owner)
                p = self.classified(check, 2, "UNVERIFIABLE")
                self.assert_counts(p, n - 1, n)
                self.assertIn(b"no grading outcome recorded", p.stderr)
            finally:
                owner.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
