"""Required case corpora are evidence: zero cases cannot certify conformance.

Run real semantic owners and the canonical execution path in a disposable copy.
Intentional corpus/source probes are repinned so DRIFT cannot masquerade as the
empty-corpus refusal. Reporter adapters and their grading contract are unchanged.
"""
from __future__ import annotations

import ast
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_conformance as runner

ROOT = Path(__file__).resolve().parent.parent

# Every affected manifest check, including shared executables and JS references.
#
# These used to carry a hand-written case count each. #73 added one vector to
# pq-key-binding-v0/rotation, the count was not carried forward, and main went red with
# `AssertionError: b'7/7' not found in b'... 8/8 cases reproduced'` -- a message about a NUMBER, on
# a test whose subject is "zero cases must not certify conformance", for a change that ADDED
# coverage. #75 carried the number; this derives it (declared_count), which keeps the positive
# control exactly as strong -- the non-empty corpus reproduces every case in it -- while removing
# the second copy that had to be maintained by hand. (#76, with @pipavlo82.)
#
# Derived from the ADMITTED INPUT, never from the adapter's output: comparing the adapter's own
# count to its own count would pass for any adapter that is merely self-consistent.
CHECKS = {
    "captured-admission-v0",
    "captured-admission-v0-review-profile",
    "captured-admission-v0-review-profile-deadline",
    "companion-envelope-v0/envelope",
    "companion-envelope-v0/envelope-reference-ts",
    "pq-key-binding-v0/cutoff",
    "pq-key-binding-v0/rotation",
    "pq-key-binding-v0/revocation",
    "pq-key-binding-v1/cutoff",
    "pq-key-binding-v1/manifest",
    "pq-key-binding-v1-profile",
    "pq-recovery-classes-v0",
    "profile-amendment-v0/amendment",
    "profile-amendment-v0/amendment-reference-ts",
    "profile-commitment-loop-v0/loop",
    "profile-commitment-loop-v0/loop-reference-ts",
    "scan-subject-binding-v0/conformance",
    "serializer-bindings/shape",
    "verdict-profile-binding-v0/binding",
    "verdict-profile-binding-v0/binding-reference-ts",
    "encode-json-utf8-lf-v0",
}

# Self-grading checks that must refuse an empty corpus but report no "N/N" summary, so there is no
# count to compare. A weaker obligation, declared separately rather than left implicit.
REDS_ON_EMPTY = {
    "predicate-conformance-v0",
    "provenance-anchor-v0/origination-gate",
    "scan-subject-binding-v0/mutation-coverage",
    *(f"{suite}/{check}"
      for suite in ("authorized-preimage-schema-v0", "consumption-time-state-binding-v0",
                    "event-time-concurrency-boundary-v0", "permission-consumption-boundary-v0")
      for check in ("conformance", "mutation-coverage")),
}

# Self-grading checks whose declared corpus is a SINGLE ARTIFACT rather than a collection of
# cases -- one anchor document, one binding-and-revocation pair, one frozen record. "Empty corpus"
# and "one result per case" are not expressible for these, so they carry neither obligation.
# Declared, because an undeclared exemption is the hole this file exists to close: a new
# single-artifact check would otherwise join the exempt side without anyone deciding it should.
SINGLE_ARTIFACT = {
    "pq-key-binding-v0/per-agent-anchor-recompute",
    "pq-key-binding-v0/revocation-deep-recompute",
    "pq-key-binding-v0/rotation-deep-recompute",
    "serializer-bindings/tsei-frozen-artifact",
}

# Self-grading checks that declare NO readable corpus at all -- no `vectors.path`, or a path that is
# not there. EMPTY, and meant to stay empty: an adapter with nothing to grade against cannot be held
# to any obligation above, so if one appears somebody has to say why in writing. Discovery used to
# `continue` past these -- a silent exemption inside the guard against silent exemptions.
# @pipavlo82 reproduced it on #77: a newcomer reporting 0/0 left all 11 tests green and the
# canonical runner called it `PASS ... 0/0 cases reproduced`. (#77 F1.)
NO_DECLARED_CORPUS: set[str] = set()
ENCODE = "encode-json-utf8-lf-v0"
CASE_KEYS = ("cases", "vectors")
# A probe case must be UNIQUE on whatever the corpus uses for identity, or the adapter reds for
# the wrong reason: the first cut of this probe duplicated an id and encode-json-utf8-lf-v0 died
# with "duplicate vector id", which proves nothing about grading. A control that reds for the
# wrong reason is not a control.
IDENTITY_KEYS = ("id", "name", "case_id", "vector_id", "case", "label", "title")


def case_collection(document):
    """-> the corpus's collection of cases, or None when it holds a single artifact instead."""
    if not isinstance(document, dict):
        return None
    for key in CASE_KEYS:
        if isinstance(document.get(key), (list, dict)):
            return document[key]
    return None


PROBE_SUFFIX = "__ungradeable_probe"


def case_template(corpus):
    """-> a representative case to copy, for either corpus shape."""
    return next(iter(corpus.values())) if isinstance(corpus, dict) else corpus[0]


def declaration_at(root, check):
    """The manifest for `check`, with a named sub-check merged over the suite-level fields."""
    suite, _, name = check.partition("/")
    directory = root / "conformance" / suite
    manifest = json.loads((directory / "suite.json").read_text(encoding="utf-8"))
    if name:
        selected = next(c for c in manifest.pop("checks") if c["name"] == name)
        manifest.update(selected)
    manifest.pop("checks", None)
    return directory, manifest


def discover_self_grading(root):
    """-> one record per declared self-grading check, in manifest order. Never skips one.

    Discovered from the MANIFEST -- not from a list kept in this file, and not by grepping the
    adapter's source for a ZERO_CASES token. `adapter.contract` is a required field the runner
    refuses to infer (run_conformance.ADAPTER_CONTRACTS), which makes it the one structural
    statement of who grades. Classifying on a token in source would reproduce the prose-coupling
    defect found in run_conformance's own precondition guard on #52.

    Each record is {"check", "corpus", "index"}, where `corpus` is:
      "cases"  -- the declared corpus holds a collection of cases
      "single" -- it holds one artifact, so there is nothing to count
      "none"   -- no readable corpus: no `vectors.path`, or the declared path is absent

    "none" is a CLASSIFICATION, not a skip. The first cut did
    `if not path or not (...).exists(): continue`. (#77 F1, @pipavlo82.)

    One record per `checks[]` ENTRY, carrying its index, so two entries sharing a name cannot
    collapse -- a dict keyed on the name merged them while the canonical runner ran both.
    (#77 F2, @pipavlo82.)

    A check whose contract is missing or unrecognised is out of scope here and cannot pass
    silently either: run_conformance:402 returns NOT COVERED, a failure, which lands in
    UNDETERMINED (exit 2).
    """
    found = []
    for suite_json in sorted((root / "conformance").glob("*/suite.json")):
        manifest = json.loads(suite_json.read_text(encoding="utf-8"))
        directory = suite_json.parent
        # The merge comes from the RUNNER, not from a copy of it here. Restating it with
        # dict.update() replaced a child's `adapter: {}` instead of inheriting, so a check the
        # canonical runner accepts as self_grading was omitted from this inventory entirely.
        # (#77 F3, @pipavlo82.) run_conformance.check_units is now the single definition.
        for index, (name, merged) in enumerate(runner.check_units(directory, manifest)):
            if (merged.get("adapter") or {}).get("contract") != "self_grading":
                continue
            path = (merged.get("vectors") or {}).get("path")
            if not path or not (directory / path).exists():
                corpus = "none"
            else:
                document = json.loads((directory / path).read_text(encoding="utf-8"))
                corpus = "cases" if case_collection(document) is not None else "single"
            found.append({"check": name, "corpus": corpus, "index": index})
    return found


def declared_count(root, check):
    """The number of cases the corpus ADMITS, read from the corpus itself."""
    directory, manifest = declaration_at(root, check)
    document = json.loads((directory / manifest["vectors"]["path"]).read_text(encoding="utf-8"))
    cases = case_collection(document)
    assert cases is not None, f"{check}: corpus declares no case collection ({CASE_KEYS})"
    return len(cases)


def pins(value):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and "sha256" in value:
            yield value
        for child in value.values():
            yield from pins(child)
    elif isinstance(value, list):
        for child in value:
            yield from pins(child)


def remove_guard(source, javascript=False):
    if javascript:
        pattern = r'if \(Array\.isArray\(doc\.vectors\) && doc\.vectors\.length === 0\) \{\n[^}]*ZERO_CASES[^}]*\}\n'
        changed, count = re.subn(pattern, "", source)
        if count != 1:
            raise ValueError("expected exactly one ZERO_CASES guard")
        return changed
    lines = source.splitlines(keepends=True)
    guards = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.If)
              and any(isinstance(s, ast.Expr) and "ZERO_CASES" in ast.get_source_segment(source, s)
                      for s in n.body)]
    if len(guards) != 1:
        raise ValueError("expected exactly one ZERO_CASES guard")
    guard = guards[0]
    return "".join(lines[:guard.lineno - 1] + lines[guard.end_lineno:])


class NonemptySelfGradingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="self-grading-corpora-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.repo = Path(cls.tmp.name) / "repo"
        shutil.copytree(ROOT, cls.repo, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.pyc"))
        cls.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        cls.flags = ["-B"] + (["-O"] if sys.flags.optimize else [])

    def declaration(self, check):
        suite, _, name = check.partition("/")
        directory = self.repo / "conformance" / suite
        manifest = json.loads((directory / "suite.json").read_text(encoding="utf-8"))
        if name:
            selected = next(c for c in manifest.pop("checks") if c["name"] == name)
            manifest.update(selected)
        return directory, manifest

    def paths(self, check):
        directory, manifest = self.declaration(check)
        return directory / manifest["vectors"]["path"], (directory / shlex.split(manifest["adapter"]["cmd"])[1]).resolve()

    def command(self, check):
        directory, manifest = self.declaration(check)
        args = shlex.split(manifest["adapter"]["cmd"])
        if args[0] in {"python", "python3"}:
            args = [sys.executable, *self.flags, *args[1:]]
        return directory, args

    def native(self, check, controls=False):
        directory, args = self.command(check)
        if controls:
            args[-1] = "--negative-controls"
        vector, _ = self.paths(check)
        return subprocess.run(args, cwd=directory, env=self.env, input=vector.read_bytes() if vector.exists() else b"",
                              capture_output=True, timeout=120)

    def canonical(self, check):
        directory, manifest = self.declaration(check)
        _, args = self.command(check)
        manifest["adapter"]["cmd"] = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
        return runner._run_one(directory, manifest, check)

    def repin(self, target):
        for path in (self.repo / "conformance").glob("*/suite.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for pin in pins(manifest):
                if (path.parent / pin["path"]).resolve() == target.resolve():
                    pin["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                    changed = True
            if changed:
                path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")

    @contextmanager
    def probe(self, check, mode, repin=True):
        vector, owner = self.paths(check)
        files = [vector, owner, *(self.repo / "conformance").glob("*/suite.json")]
        original = {p: p.read_bytes() for p in files}
        document = json.loads(original[vector])
        key = "cases" if "cases" in document else "vectors"
        try:
            if mode == "missing":
                vector.unlink()
            elif mode == "malformed":
                vector.write_bytes(b'{"cases":')
            else:
                corpus = document[key]
                if mode == "empty":
                    document[key] = {} if isinstance(corpus, dict) else []
                elif mode == "null":
                    document[key] = None
                elif mode == "ungradeable":
                    # One case the corpus ADMITS but the adapter cannot grade: a copy of a real
                    # case, unique on every identity field, with the expectation REMOVED. The
                    # corpus declares N+1; at most N can be checked. Nothing may call that a pass.
                    extra = copy.deepcopy(case_template(corpus))
                    graded = next(k for k in extra if "expect" in k.lower())
                    extra.pop(graded)
                    for field in list(extra):
                        if field.lower() in IDENTITY_KEYS and isinstance(extra[field], str):
                            extra[field] = extra[field] + PROBE_SUFFIX
                    if isinstance(corpus, dict):
                        document[key] = {**corpus, PROBE_SUFFIX: extra}
                    else:
                        document[key] = [*corpus, extra]
                elif mode == "duplicate":
                    # One MORE case, still a passing one. Proves the expectation follows the
                    # corpus instead of a literal: the adapter must grade N+1 and the derived
                    # count must move with it.
                    if isinstance(corpus, dict):
                        first = next(iter(corpus))
                        document[key] = {**corpus, f"{first}__duplicate": copy.deepcopy(corpus[first])}
                    else:
                        extra = copy.deepcopy(corpus[0])
                        if isinstance(extra.get("name"), str):
                            extra["name"] = extra["name"] + "__duplicate"
                        document[key] = [*corpus, extra]
                elif mode == "refuted":
                    case = next(iter(corpus.values())) if isinstance(corpus, dict) else corpus[0]
                    if check == ENCODE:
                        case["expect"]["byte_length"] += 1
                    elif "expected_verdict" in case:
                        case["expected_verdict"] = "__WRONG_VERDICT__"
                    else:
                        field = "expect" if "expect" in case else "expected"
                        expected = case[field]
                        if isinstance(expected, dict):
                            expected[next(iter(expected))] = "__WRONG_RESULT__"
                        else:
                            case[field] = "__WRONG_RESULT__"
                vector.write_text(json.dumps(document, ensure_ascii=True), encoding="utf-8", newline="\n")
            if repin and vector.exists():
                self.repin(vector)
            yield vector, owner
        finally:
            for path, data in original.items():
                path.write_bytes(data)

    def assert_empty(self, check, controls=False):
        process = self.native(check, controls)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertIn(b"ZERO_CASES", process.stderr)
        self.assertNotIn(b"PASS", process.stdout)
        self.assertNotIn(b"NEGATIVE CONTROL RED", process.stdout)
        result = self.canonical(check)
        self.assertEqual((result.ok, result.kind), (False, "UNVERIFIABLE"), result.detail)
        self.assertIn("ZERO_CASES", result.detail)
        self.assertEqual(runner.exit_code_for_failures([result]), 2)

    def test_nonempty_corpora_reproduce(self):
        for check in sorted(CHECKS):
            with self.subTest(check=check):
                # The expectation comes from the corpus in the disposable copy, so a vector added
                # to any of these needs no second edit here, and a corpus the adapter only
                # partly grades still reds.
                count = declared_count(self.repo, check)
                process = self.native(check)
                self.assertEqual(process.returncode, 0, process.stderr)
                if check == "scan-subject-binding-v0/conformance":
                    result = json.loads(process.stdout)
                    self.assertEqual((result["total"], result["reproduced"]), (count, count))
                else:
                    self.assertIn(f"{count}/{count}".encode(), process.stdout)

    def test_derived_count_tracks_the_corpus(self):
        """The derived count must follow the corpus, or it is a literal with extra steps.

        Adding a case to the corpus WITHOUT touching this file must still be graded: the adapter
        reports N+1/N+1 and the derived expectation moves with it. The control is that the OLD
        count then no longer appears, which is what the hand-written table could not survive.
        """
        check = "pq-key-binding-v0/rotation"
        before = declared_count(self.repo, check)
        with self.probe(check, "duplicate"):
            after = declared_count(self.repo, check)
            self.assertEqual(after, before + 1)
            process = self.native(check)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn(f"{after}/{after}".encode(), process.stdout)
            self.assertNotIn(f"{before}/{before}".encode(), process.stdout)

    def test_every_admitted_case_must_be_checked(self):
        """A non-empty declared corpus produces exactly one checked result per case.

        @pipavlo82's invariant on #76, and the half the derived count alone does not reach. With a
        derived expectation, an adapter that grades 7 of 8 and REPORTS 7/7 is already caught --
        8 != 7. What is not caught is an adapter whose total comes from the corpus length rather
        than from results it actually checked: it prints 8/8 while grading 7, and agrees with
        itself. `cutoff_enforce.py` used to compute exactly that way
        (`len(fx['cases']) - fails}/{len(fx['cases'])}`), saved only by raising KeyError on the
        missing field; since #82/#83 the adapters count graded outcomes via `Grading`, and this test
        guards against that accounting being removed again.

        So: admit a case the adapter CANNOT grade and require that nothing calls the run a pass.

        The signal is the EXIT CODE, deliberately, and not a printed "a/b". A first cut also
        rejected any `N+1/N+1` in stdout and went red on encode-json-utf8-lf-v0, whose
        "Cross-language agreement: 49/49 vectors" line is two implementations agreeing they could
        not classify the case -- not a grade claim. Telling those apart needs prose-matching, which
        is the coupling this repo keeps getting bitten by. The removal control below shows the exit
        code is sufficient: a skipping adapter exits 0.
        """
        for check in sorted(CHECKS):
            with self.subTest(check=check):
                admitted = declared_count(self.repo, check) + 1
                with self.probe(check, "ungradeable"):
                    self.assertEqual(declared_count(self.repo, check), admitted,
                                     "the probe did not reach the corpus, so this proves nothing")
                    # NOT controls=: --negative-controls is a different path that does not grade
                    # the corpus at all, so it would pass here while establishing nothing.
                    process = self.native(check)
                    self.assertNotEqual(process.returncode, 0,
                                        "a corpus case that cannot be graded was reported as a pass:\n"
                                        + (process.stdout + process.stderr).decode(errors="replace"))

    def test_an_adapter_that_skips_an_admitted_case_is_caught(self):
        """Removal control for the test above, against a REAL adapter.

        Since #82/#83 the adapters keep completeness accounting themselves: `Grading.expectation`
        records a case with no expectation as ungradable and `Grading.finish` turns any ungradable
        case into exit 2. So a one-line skip no longer produces a false pass, and the original
        control (which expected one) went stale -- @pipavlo82's composition audit of #78 + #82 + #83.

        Two halves, both against cutoff_enforce.py:
        1. Unchanged adapter: the probe case stays UNVERIFIABLE (exit 2, named in stderr).
        2. Completeness enforcement removed (`finish()` replaced by a refutation-only exit): the
           same probe now exits 0 -- the false pass the test above refuses.
        Without (2) the test above would only be re-testing the adapter's own accounting.
        """
        check = "pq-key-binding-v0/rotation"
        _, owner = self.paths(check)
        source = owner.read_text(encoding="utf-8")
        anchor = "    return grading.finish()\n"
        self.assertEqual(source.count(anchor), 1,
                         "control anchor not found exactly once; enforcement was not removed, "
                         "so this control proves nothing")
        with self.probe(check, "ungradeable"):
            process = self.native(check)
            output = (process.stdout + process.stderr).decode(errors="replace")
            self.assertEqual(process.returncode, 2,
                             "an ungradable case must stay UNVERIFIABLE (exit 2):\n" + output)
            self.assertIn(b"UNVERIFIABLE: UNGRADABLE_CASE", process.stderr, output)
            self.assertIn(PROBE_SUFFIX.encode(), process.stderr,
                          "the UNVERIFIABLE line must name the probe case, not some other case")
        with self.probe(check, "ungradeable"):
            owner.write_text(source.replace(anchor, "    return 1 if grading.refuted else 0\n", 1),
                             encoding="utf-8", newline="\n")
            self.repin(owner)
            process = self.native(check)
            # completeness gone: the adapter calls a corpus with an ungraded case a pass
            self.assertEqual(process.returncode, 0,
                             "removing completeness enforcement did not restore the false pass:\n"
                             + (process.stdout + process.stderr).decode(errors="replace"))

    def test_every_self_grading_check_is_declared(self):
        """No self-grading check may silently escape this file.

        The four sets above are obligations, not an inventory: CHECKS reproduces a counted corpus,
        REDS_ON_EMPTY must refuse an empty one, SINGLE_ARTIFACT has no corpus to count, and
        NO_DECLARED_CORPUS has no corpus at all and has to be argued for. A new check must land in
        exactly one, and this is what makes that happen rather than being remembered -- the same
        class as #57/#65/#66, where a sweep that enumerates what exists exempts whatever is in
        flight. (@pipavlo82 on #76: "a newly discovered self-grading suite must not silently escape
        this check.")
        """
        records = discover_self_grading(self.repo)
        self.assertTrue(records, "discovered no self-grading checks at all -- the sweep is broken, "
                                 "and a sweep that finds nothing proves nothing")
        self.assert_partition(records, "the repo")

    def assert_partition(self, records, where, declared=None, sets=None):
        """Every record in exactly one declared set, and no two records sharing an identity.

        `declared`/`sets` exist so a control can drive this rule over a SYNTHETIC manifest tree.
        The repo call passes neither and gets the real four sets; a control over a one-suite
        fixture passes its own, because otherwise the bidirectional stale check fires on the 36
        real declarations the fixture does not contain and masks the property under test.
        """
        if sets is None:
            sets = {"CHECKS": CHECKS, "REDS_ON_EMPTY": REDS_ON_EMPTY,
                    "SINGLE_ARTIFACT": SINGLE_ARTIFACT, "NO_DECLARED_CORPUS": NO_DECLARED_CORPUS}
        if declared is None:
            declared = set().union(*sets.values()) if sets else set()
        single = sets.get("SINGLE_ARTIFACT", set())
        no_corpus = sets.get("NO_DECLARED_CORPUS", set())
        names = [r["check"] for r in records]

        # F2: two checks[] entries sharing a name produce two records here. A dict keyed on the
        # name merged them, and the suite could not tell them apart, while the canonical runner ran
        # both and labelled both results identically.
        duplicates = sorted({n for n in names if names.count(n) > 1})
        self.assertFalse(duplicates, f"{where}: duplicate self-grading check identities "
                         f"{duplicates}. Two checks[] entries share a name, so their results are "
                         "indistinguishable by label -- give each check a distinct name.")

        # BIDIRECTIONAL. discovered-minus-declared below, and declared-minus-discovered here: a
        # removed check leaves its declaration behind, and an inventory that only checks one
        # direction slowly fills with names for things that no longer exist. This assertion was
        # present at 3ff9d09 and I DELETED it while rewriting this method for F1/F2 — the test
        # count did not change, so nothing flagged it. (#77 F4, @pipavlo82.)
        stale = sorted(declared - set(names))
        self.assertFalse(stale, f"{where}: declared here but no longer a discovered self-grading "
                         f"check: {stale}. Remove the declaration, or restore the check.")

        undeclared = sorted(set(names) - declared)
        self.assertFalse(undeclared, f"{where}: self-grading checks in none of the four sets: "
                         f"{undeclared}. Add each to CHECKS (if it reports N/N over a case "
                         "corpus), REDS_ON_EMPTY (if it must refuse an empty corpus but reports no "
                         "count), SINGLE_ARTIFACT (if its corpus is one document), or "
                         "NO_DECLARED_CORPUS (if it declares no readable corpus -- and say why).")

        pairs = [(a, b) for i, a in enumerate(sets) for b in list(sets)[i + 1:]]
        for a, b in pairs:
            overlap = sets[a] & sets[b]
            self.assertFalse(overlap, f"{sorted(overlap)} declared in both {a} and {b}; "
                                      "the obligations differ, so one check cannot carry both")

        # And the split must match what the corpora actually are, not what we remember them to be.
        for r in records:
            with self.subTest(check=r["check"]):
                if r["check"] in single:
                    self.assertEqual(r["corpus"], "single", f"{r['check']} is declared "
                                     f"SINGLE_ARTIFACT but its corpus is {r['corpus']!r}")
                elif r["check"] in no_corpus:
                    self.assertEqual(r["corpus"], "none", f"{r['check']} is declared "
                                     f"NO_DECLARED_CORPUS but its corpus is {r['corpus']!r} -- it "
                                     "owes the matching obligation")
                else:
                    self.assertEqual(r["corpus"], "cases", f"{r['check']} carries a case "
                                     f"obligation but its corpus is {r['corpus']!r}")

    SELF_GRADING_ADAPTER = {"kind": "stdio", "cmd": "true", "contract": "self_grading"}

    def _synthetic_repo(self, tmp, suites):
        """A minimal tree holding only conformance/<name>/suite.json, to drive discovery alone.

        Deliberately NOT self.repo: these controls add and break manifests, and self.repo is shared
        with every other test in this class.
        """
        root = Path(tmp)
        for name, manifest in suites.items():
            d = root / "conformance" / name
            d.mkdir(parents=True)
            (d / "suite.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        return root

    def test_self_grading_without_a_corpus_is_classified_not_skipped(self):
        """#77 F1 control. A newcomer with no vectors.path must be classified, then reported.

        Reproduced by @pipavlo82 at 3ff9d09 and again here before the fix: such a suite was skipped
        by discovery, left all 11 tests green, and the canonical runner reported
        `PASS newcomer-noc-v0 0/0 cases reproduced` -- zero cases certifying conformance, which is
        the exact failure this file exists to prevent.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = self._synthetic_repo(tmp, {"newcomer-no-corpus-v0": {
                "profile": "newcomer-no-corpus-v0", "adapter": self.SELF_GRADING_ADAPTER}})
            records = discover_self_grading(root)
            self.assertEqual([r["check"] for r in records], ["newcomer-no-corpus-v0"],
                             "a self-grading check with no vectors.path was dropped by discovery")
            self.assertEqual(records[0]["corpus"], "none")
            # classified is not enough: being in no declared set, it must then be REPORTED
            with self.assertRaises(AssertionError) as caught:
                self.assert_partition(records, "synthetic", sets={})
            self.assertIn("none of the four sets", str(caught.exception))
            self.assertIn("newcomer-no-corpus-v0", str(caught.exception))

    def test_two_checks_sharing_a_name_do_not_collapse(self):
        """#77 F2 control. Duplicate checks[] names must be reported, not merged.

        Reproduced by @pipavlo82 at 3ff9d09: duplicating the rotation check left 11/11 green while
        the canonical runner executed both.
        """
        vectors = {"path": "v.json", "sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            root = self._synthetic_repo(tmp, {"dup-v0": {
                "profile": "dup-v0", "adapter": self.SELF_GRADING_ADAPTER,
                "checks": [{"name": "same", "vectors": vectors},
                           {"name": "same", "vectors": vectors}]}})
            (root / "conformance" / "dup-v0" / "v.json").write_text(
                json.dumps({"cases": [{"name": "a", "expected": {}}]}) + "\n", encoding="utf-8")
            records = discover_self_grading(root)
            self.assertEqual(len(records), 2, "two checks[] entries must produce two records")
            self.assertEqual([r["index"] for r in records], [0, 1],
                             "records must carry their manifest index or they cannot be told apart")
            with self.assertRaises(AssertionError) as caught:
                self.assert_partition(records, "synthetic", sets={})
            self.assertIn("duplicate self-grading check identities", str(caught.exception))

    def test_a_child_inheriting_the_adapter_is_discovered(self):
        """#77 F3 control. `adapter: {}` inherits the suite-level adapter, as the runner does.

        The runner's merge is asymmetric (run_conformance.check_units): the child's adapter wins
        only when TRUTHY, so an empty one inherits. Restating that merge here with dict.update()
        replaced it instead, and a check the canonical runner accepts as self_grading was omitted
        from this inventory while all 13 tests stayed green. Discovery now calls the runner's own
        merge, so the two cannot diverge again.
        """
        vectors = {"path": "v.json", "sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as tmp:
            root = self._synthetic_repo(tmp, {"inherit-v0": {
                "profile": "inherit-v0",
                "adapter": self.SELF_GRADING_ADAPTER,          # declared at suite level
                "checks": [{"name": "child", "vectors": vectors, "adapter": {}}]}})
            (root / "conformance" / "inherit-v0" / "v.json").write_text(
                json.dumps({"cases": [{"name": "a", "expected": {}}]}) + "\n", encoding="utf-8")

            # the runner treats it as self_grading ...
            _, merged = runner.check_units(root / "conformance" / "inherit-v0",
                                           json.loads((root / "conformance" / "inherit-v0"
                                                       / "suite.json").read_text()))[0]
            self.assertEqual((merged.get("adapter") or {}).get("contract"), "self_grading",
                             "the runner's own merge no longer inherits a falsy child adapter; "
                             "this control is testing the wrong thing")
            # ... so discovery must too, and must then report it as undeclared
            records = discover_self_grading(root)
            self.assertEqual([r["check"] for r in records], ["inherit-v0/child"],
                             "a child inheriting the suite adapter was dropped by discovery")
            with self.assertRaises(AssertionError) as caught:
                self.assert_partition(records, "synthetic", sets={})
            self.assertIn("inherit-v0/child", str(caught.exception))

    def test_a_declaration_with_no_discovered_check_is_reported(self):
        """#77 F4 control. Coverage is bidirectional: a removed check must not leave a declaration.

        This assertion existed at 3ff9d09 and I deleted it while rewriting the partition method for
        F1/F2. The test-method count was unchanged, so nothing caught it.
        """
        records = [{"check": "real-v0", "corpus": "cases", "index": 0}]
        with self.assertRaises(AssertionError) as caught:
            self.assert_partition(records, "synthetic",
                                 sets={"CHECKS": {"real-v0", "removed-v0"}})
        self.assertIn("no longer a discovered self-grading check", str(caught.exception))
        self.assertIn("removed-v0", str(caught.exception))
        self.assertNotIn("real-v0'", str(caught.exception))

    def test_repinned_empty_is_unverifiable(self):
        for check in CHECKS:
            with self.subTest(check=check), self.probe(check, "empty"):
                self.assert_empty(check)

    def test_stale_pin_is_drift_not_empty_refusal(self):
        for check in CHECKS:
            with self.subTest(check=check), self.probe(check, "empty", repin=False):
                result = self.canonical(check)
                self.assertEqual((result.ok, result.kind), (False, "DRIFT"), result.detail)
                self.assertNotIn("ZERO_CASES", result.detail)

    def test_malformed_and_missing_are_not_empty(self):
        for check in CHECKS:
            for mode in ("malformed", "null", "missing"):
                with self.subTest(check=check, mode=mode), self.probe(check, mode):
                    process = self.native(check)
                    self.assertNotEqual(process.returncode, 0)
                    self.assertFalse(any(line.startswith(b"UNVERIFIABLE") and b"ZERO_CASES" in line
                                         for line in (process.stdout + process.stderr).splitlines()))
                    result = self.canonical(check)
                    self.assertFalse(result.ok)
                    self.assertEqual(result.kind, "NOT COVERED" if mode == "missing" else "SUITE", result.detail)

    def test_real_semantic_mismatch_is_exit_one(self):
        for check in CHECKS:
            with self.subTest(check=check), self.probe(check, "refuted"):
                process = self.native(check)
                self.assertEqual(process.returncode, 1, process.stderr)
                self.assertNotIn(b"Traceback", process.stderr)
                self.assertNotIn(b"ZERO_CASES", process.stdout + process.stderr)
                result = self.canonical(check)
                self.assertEqual((result.ok, result.kind), (False, "SUITE"), result.detail)

    def test_each_guard_prevents_old_false_success(self):
        seen = set()
        for check in CHECKS:
            _, owner = self.paths(check)
            if owner in seen:
                continue
            seen.add(owner)
            with self.subTest(check=check), self.probe(check, "empty"):
                owner.write_text(remove_guard(owner.read_text(encoding="utf-8"), owner.suffix == ".mjs"),
                                 encoding="utf-8", newline="\n")
                self.repin(owner)
                process = self.native(check, controls=check == ENCODE)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertNotIn(b"ZERO_CASES", process.stdout + process.stderr)
                if check == ENCODE:
                    self.assertIn(b"PASS negative controls: 6/6", process.stdout)
                else:
                    self.assertTrue(self.canonical(check).ok)

    def test_encode_controls_require_cases_too(self):
        with self.probe(ENCODE, "empty"):
            self.assert_empty(ENCODE, controls=True)

    def test_existing_nonempty_requirements_remain_red(self):
        for check in sorted(REDS_ON_EMPTY):
            with self.subTest(check=check), self.probe(check, "empty"):
                self.assertNotEqual(self.native(check).returncode, 0)
                self.assertFalse(self.canonical(check).ok)

    def test_no_bytecode_in_disposable_copy(self):
        self.assertEqual(list(self.repo.rglob("*.pyc")), [])


if __name__ == "__main__":
    unittest.main()
