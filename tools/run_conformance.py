#!/usr/bin/env python3
"""Run every conformance suite exactly as its own suite.json declares.

The suite manifest is the contract, so this reads it rather than assuming:

    adapter.cmd       the command, run with the suite directory as cwd
    adapter.kind      "stdio" -> the vectors file is fed on STDIN
    adapter.contract  WHO GRADES (required; no inference from --grade, output shape or exit code):
                      "self_grading" -- the adapter compares against its own declared expectations; its exit code is
                                        the verdict (0 reproduced, 1 refuted, 2 could not conclude).
                      "reporter"     -- the adapter only reports results; exit 0 means a report was produced, nothing
                                        more. The RUNNER compares every result with the pinned vectors[].expected
                                        (bin/conformance-suite's comparison) and fails missing, extra or invalid output
                                        as REPORT_CONTRACT. A valid pin never waives this grading.
    vectors.path    the vectors, and vectors.sha256 if pinned
    spec.sha256     the spec digest, if pinned

Two rules this runner holds itself to, because a conformance runner that gets
them wrong is worse than none at all:

1. NO SILENT SKIPS. A suite directory with no manifest, a missing vectors file,
   or an adapter kind we do not implement is reported as NOT COVERED and fails
   the run. A suite that quietly does not execute is indistinguishable from one
   that passes, which is the exact defect the suites exist to detect.

2. A NON-ZERO EXIT MUST BE ATTRIBUTABLE. Every failure prints whether it was the
   suite that failed or the runner that could not run it — a missing interpreter
   and a refuted vector are both "red", and conflating them wastes the signal.

EXIT CODES follow this repo's own tri-state convention (bin/recompute-step:13,
"couldn't check is its own verdict, never a pass"), because the exit code is the only
channel CI actually reads and collapsing "could not run" into "failed" accuses the
evidence of a fault in the environment:

    0  every suite ran and reproduced
    1  verified-bad — a suite ran and refuted, or a pinned digest determinately mismatched
    2  UNVERIFIABLE — something could not be run at all (missing tool or dependency,
       timeout, a suite nobody declared). Never a pass, and never a refutation either.

A determinate failure outranks an undetermined one: if anything genuinely refuted, that is
exit 1 even when other suites could not run, so a real break is never softened to "unknown".
"""

from __future__ import annotations

from dataclasses import dataclass
import decimal
import hashlib
import json
import math
import re
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFORMANCE = ROOT / "conformance"


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# Which failure kinds are a determinate verdict (exit 1) and which mean we could not
# conclude at all (exit 2). RUNNER and NOT COVERED are not evidence about the vectors.
DETERMINATE = {"SUITE", "DRIFT"}
UNDETERMINED = {"RUNNER", "NOT COVERED", "UNDECLARED", "UNVERIFIABLE", "REPORT_CONTRACT"}
# REPORT_CONTRACT: a reporter-contract adapter did not complete the reporter protocol (missing / extra / invalid / empty
# report, a nonzero reporter exit, an invalid corpus). It cannot establish the vectors (exit 2), it is attributed to the
# implementation under test rather than the environment, and it is deliberately NOT "NOT COVERED": the uncovered.json
# pass rewrites NOT COVERED on a declared suite to NOT RUN (build-silent), so a reporter that drops the vectors it gets
# wrong must never be able to reach that rewrite.
ADAPTER_CONTRACTS = ("reporter", "self_grading")

# These signatures identify failures in the command/runtime/dependency layer, before an
# adapter can answer its conformance question. Keep them specific: generic words such as
# "error", "failed", "package", or "unexpected" also occur in legitimate suite verdicts.
ENVIRONMENT_FAILURE_SIGNATURES = (
    "Unexpected while resolving package",
    "Cannot find module",
    "Cannot find package",
    "ModuleNotFound",
    "ImportError",
    "No module named",
    "command not found",
    "not recognized as an internal or external command",
    "is not recognized as a name of a cmdlet",
    "ENOENT",
)


class Result:
    def __init__(self, name: str, ok: bool, kind: str, detail: str):
        self.name, self.ok, self.kind, self.detail = name, ok, kind, detail


@dataclass(frozen=True)
class ProcessFailure:
    kind: str
    detail: str


def _last_process_diagnostic(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    # A crashing runtime prints its own banner last ("Bun v1.3.14 (Linux x64)"), which says
    # nothing about why. Report the diagnostic line, not the footer.
    noise = ("Bun v", "at ", "^", "|")
    signal = [line for line in lines if not line.lstrip().startswith(noise)]
    return (signal[-1] if signal else (lines[-1] if lines else "(no output)"))[:110]


def classify_process_failure(returncode: int, output: str, cmd: str) -> ProcessFailure:
    """Attribute one non-zero adapter process exit without judging vector semantics."""
    if returncode == 0:
        raise ValueError("classify_process_failure requires a non-zero return code")
    if returncode in (126, 127):
        return ProcessFailure(
            "RUNNER",
            f"command could not execute ({returncode}) — interpreter missing or unavailable: {cmd}",
        )
    last = _last_process_diagnostic(output)
    if any(signature in output for signature in ENVIRONMENT_FAILURE_SIGNATURES):
        return ProcessFailure("RUNNER", f"environment, not evidence: {last}")
    if returncode == 2:
        # The gate's own tri-state verdict: it ran and could not conclude (empty corpus,
        # missing optional lane, validator fault). Scoring it as refuted would accuse the
        # vectors of a fault the gate explicitly said it could not check.
        return ProcessFailure("UNVERIFIABLE", f"gate could not conclude (exit 2): {last}")
    return ProcessFailure("SUITE", f"exit {returncode}: {last}")


def exit_code_for_failures(failures: list[Result]) -> int:
    """Apply repository precedence: determinate refutation outranks could-not-run."""
    if not failures:
        return 0
    return 1 if any(result.kind in DETERMINATE for result in failures) else 2


def run_suite(d: pathlib.Path) -> list:
    manifest = d / "suite.json"
    if not manifest.is_file():
        return [Result(d.name, False, "NOT COVERED", "no suite.json — nothing declares how to run this")]

    try:
        m = json.loads(manifest.read_text())
    except Exception as e:
        return [Result(d.name, False, "RUNNER", f"suite.json is not valid JSON: {e}")]

    # A suite may declare several independent checks (each with its own vectors, digest and
    # adapter) instead of one. Reported per check: "pq-key-binding-v0 failed" would hide
    # WHICH of grade/cutoff/rotation/revocation refuted, and a failure that cannot name
    # itself is most of the way back to the problem this runner exists to fix.
    if isinstance(m.get("checks"), list) and m["checks"]:
        out = []
        for c in m["checks"]:
            nm = f"{d.name}/{c.get('name') or '?'}"
            sub = dict(m)
            sub.pop("checks", None)
            sub["vectors"] = c.get("vectors")
            if c.get("adapter"):
                sub["adapter"] = c["adapter"]
            out.append(_run_one(d, sub, nm))
        return out

    return [_run_one(d, m, d.name)]


_HEX64 = re.compile(r"[0-9a-f]{64}")


def _check_declared_pins(d: pathlib.Path, m: dict):
    """A pin the suite declares for its checker, mutation checker or dependencies is part of the claim,
    same as vectors.sha256 and spec.sha256: a stale pin must fail here, not pass silently."""
    # A key that is absent declares nothing. A key that is PRESENT declares a pin, and a declared pin that
    # cannot be enforced (bare string, empty or non-hex sha256, a typo such as "sha265") is NOT COVERED,
    # never skipped: skipping it would read as enforced. Extra annotation keys (e.g. "note") are allowed.
    pins = [(k, m[k]) for k in ("checker", "mutation_checker") if k in m]
    if "dependencies" in m:
        deps = m["dependencies"]
        if not isinstance(deps, list):
            return "NOT COVERED", f"dependencies declared but not a list of {{path, sha256}} pins: {deps!r:.80}"
        pins += [("dependencies", x) for x in deps]
    for key, entry in pins:
        if not (isinstance(entry, dict) and isinstance(entry.get("path"), str) and entry["path"]
                and isinstance(entry.get("sha256"), str) and _HEX64.fullmatch(entry["sha256"])):
            return "NOT COVERED", (f"{key} pin declared but malformed (need {{path, sha256: 64 lowercase hex}}), "
                                   f"so it cannot be enforced: {entry!r:.120}")
        f = d / entry["path"]
        if not f.is_file():
            return "NOT COVERED", f"{key} declared but missing: {entry['path']}"
        actual = sha256(f)
        if actual != entry["sha256"]:
            return "DRIFT", f"{key} {entry['path']} sha256 {actual[:16]}… != pinned {entry['sha256'][:16]}…"
    return None


def _run_one(d: pathlib.Path, m: dict, label: str) -> Result:

    adapter = m.get("adapter") or {}
    cmd = adapter.get("cmd")
    kind = adapter.get("kind", "")
    if not cmd:
        return Result(label, False, "NOT COVERED", "declares no adapter.cmd")

    # pinned digests are part of the claim: drift means the vectors under test
    # are not the vectors that were reviewed
    vectors = m.get("vectors")
    vec_path = None
    if isinstance(vectors, dict):
        vec_path = vectors.get("path")
        pinned = vectors.get("sha256")
        if vec_path:
            vf = d / vec_path
            if not vf.is_file():
                return Result(label, False, "NOT COVERED", f"vectors declared but missing: {vec_path}")
            if pinned:
                actual = sha256(vf)
                if actual != pinned:
                    return Result(label, False, "DRIFT",
                                  f"{vec_path} sha256 {actual[:16]}… != pinned {pinned[:16]}…")

    spec = m.get("spec")
    if isinstance(spec, dict) and spec.get("path") and spec.get("sha256"):
        sf = d / spec["path"]
        if not sf.is_file():
            # A declared + pinned spec that is absent cannot have its pin verified — the same silent
            # skip the vectors branch above already guards. Rule 1 of this runner is NO SILENT SKIPS:
            # report it as its own verdict, never fall through and run the adapter as if the pin held.
            return Result(label, False, "NOT COVERED", f"spec declared but missing: {spec['path']}")
        actual = sha256(sf)
        if actual != spec["sha256"]:
            return Result(label, False, "DRIFT",
                          f"{spec['path']} sha256 {actual[:16]}… != pinned {spec['sha256'][:16]}…")

    pin_failure = _check_declared_pins(d, m)
    if pin_failure is not None:
        return Result(label, False, pin_failure[0], pin_failure[1])

    if kind and kind != "stdio":
        return Result(label, False, "NOT COVERED", f"adapter.kind '{kind}' not implemented by this runner")

    contract = adapter.get("contract")
    if contract not in ADAPTER_CONTRACTS:
        # No implicit third contract and no inference from --grade / output shape / exit code: an adapter that does not
        # say who grades cannot be graded, so it is not run as if it had said.
        return Result(label, False, "NOT COVERED",
                      f"adapter.contract must be one of {'/'.join(ADAPTER_CONTRACTS)}, got {contract!r}")

    stdin_data = b""
    if vec_path:
        stdin_data = (d / vec_path).read_bytes()

    if contract == "reporter":
        return _run_reporter(d, cmd, label, stdin_data, vec_path)

    try:
        proc = subprocess.run(cmd, shell=True, cwd=d, input=stdin_data,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    except subprocess.TimeoutExpired:
        return Result(label, False, "RUNNER", "timed out after 300s")
    except Exception as e:
        return Result(label, False, "RUNNER", f"could not execute adapter.cmd: {e}")

    out = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        failure = classify_process_failure(proc.returncode, out, cmd)
        return Result(label, False, failure.kind, failure.detail)
    return Result(label, True, "SUITE", _last_process_diagnostic(out))


def _grader_canon():
    """The comparison representation of bin/conformance-suite (sorted compact JSON, ensure_ascii=False), imported rather
    than copied so the canonical runner and the standalone grader cannot drift apart."""
    import importlib.machinery, importlib.util
    loader = importlib.machinery.SourceFileLoader("_conformance_suite_grader", str(ROOT / "bin" / "conformance-suite"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod.canon


class _Invalid(Exception):
    pass


def _strict_json(data: bytes, what: str):
    """UTF-8 JSON, one document, no duplicate object members at any depth, no NaN/Infinity,
    no number token that the parser would round (overflow to inf, underflow to 0, precision beyond a double)."""
    def no_dupes(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise _Invalid(f"{what}: duplicate member {k!r}")
            obj[k] = v
        return obj

    def no_const(c):
        raise _Invalid(f"{what}: non-JSON number {c}")

    def exact_float(tok):
        # Grading compares parsed values, so a token the parser rounds is evidence lost before comparison:
        # 1e999 and 2e999 both become inf, 1e-999 and 2e-999 both become 0.0. Accept a number token only when
        # its decimal value is exactly the double it parses to, or that double's shortest repr.
        f = float(tok)
        if not math.isfinite(f):
            raise _Invalid(f"{what}: number {tok[:40]} overflows to a non-finite value")
        d = decimal.Decimal(tok)
        if d != decimal.Decimal(repr(f)) and d != decimal.Decimal(f):
            raise _Invalid(f"{what}: number {tok[:40]} is not exactly representable (parses to {f!r})")
        return f
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise _Invalid(f"{what}: not UTF-8 ({e.reason})")
    try:
        return json.loads(text, object_pairs_hook=no_dupes, parse_constant=no_const, parse_float=exact_float)
    except _Invalid:
        raise
    except ValueError as e:
        raise _Invalid(f"{what}: not a single JSON document ({e.msg} at {e.pos})")


def _reporter_corpus(stdin_data: bytes):
    """-> list of (name, vector) for a reporter check. Rejects what cannot be graded unambiguously."""
    canon = _grader_canon()
    c = _strict_json(stdin_data, "INVALID_CORPUS")
    if not isinstance(c, dict) or not isinstance(c.get("vectors"), list):
        raise _Invalid("INVALID_CORPUS: a reporter corpus is an object with a \"vectors\" array")
    if not c["vectors"]:
        raise _Invalid("EMPTY_CORPUS: no vectors, and 0/0 is not a pass")
    seen, out = set(), []
    for i, v in enumerate(c["vectors"]):
        if not isinstance(v, dict) or not isinstance(v.get("name"), str) or not v["name"]:
            raise _Invalid(f"INVALID_CORPUS: vectors[{i}] needs a nonempty string name")
        if v["name"] == "results":
            raise _Invalid("INVALID_CORPUS: \"results\" is reserved (it is the report envelope key)")
        if v["name"] in seen:
            raise _Invalid(f"INVALID_CORPUS: duplicate vector name {v['name']!r}")
        if "expected" not in v:
            raise _Invalid(f"INVALID_CORPUS: vector {v['name']!r} declares no expected")
        if "must_not_equal" in v and canon(v["expected"]) == canon(v["must_not_equal"]):
            raise _Invalid(f"INVALID_CORPUS: vector {v['name']!r} expects the value it forbids (must_not_equal)")
        seen.add(v["name"])
        out.append((v["name"], v))
    return out


def _run_reporter(d: pathlib.Path, cmd: str, label: str, stdin_data: bytes, vec_path) -> Result:
    """REPORTER contract: exit 0 means only that a report was produced; the runner compares every result with the
    pinned vectors[].expected. stdout carries exactly one JSON report (a name->result map, or {"results": map});
    stderr is diagnostics and is never parsed."""
    if not vec_path:
        return Result(label, False, "REPORT_CONTRACT", "INVALID_CORPUS: a reporter check must declare vectors")
    try:
        vectors = _reporter_corpus(stdin_data)
    except _Invalid as e:
        return Result(label, False, "REPORT_CONTRACT", str(e))
    try:
        proc = subprocess.run(cmd, shell=True, cwd=d, input=stdin_data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    except subprocess.TimeoutExpired:
        return Result(label, False, "RUNNER", "timed out after 300s")
    except Exception as e:
        return Result(label, False, "RUNNER", f"could not execute adapter.cmd: {e}")
    combined = (proc.stdout + b"\n" + proc.stderr).decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        failure = classify_process_failure(proc.returncode, combined, cmd)
        if failure.kind == "RUNNER":
            return Result(label, False, "RUNNER", failure.detail)
        # A nonzero reporter exit is not a self-graded refutation: the reporter protocol was not completed.
        return Result(label, False, "REPORT_CONTRACT",
                      f"ADAPTER_FAILED: reporter exited {proc.returncode} ({_last_process_diagnostic(combined)})")
    if not proc.stdout.strip():
        return Result(label, False, "REPORT_CONTRACT", "EMPTY_REPORT: exit 0 with no report on stdout")
    try:
        report = _strict_json(proc.stdout, "INVALID_REPORT")
    except _Invalid as e:
        return Result(label, False, "REPORT_CONTRACT", str(e))
    if not isinstance(report, dict):
        return Result(label, False, "REPORT_CONTRACT", "INVALID_REPORT: the report must be a JSON object")
    if list(report) == ["results"]:
        report = report["results"]
        if not isinstance(report, dict):
            return Result(label, False, "REPORT_CONTRACT", "INVALID_REPORT: \"results\" must be a name->result object")

    canon = _grader_canon()
    declared = {n for n, _ in vectors}
    missing = sorted(declared - set(report))
    extra = sorted(set(report) - declared)
    refuted = []
    for name, v in vectors:
        if name not in report:          # membership is tested apart from value: absent is never null
            continue
        got = report[name]
        if canon(got) != canon(v["expected"]):
            refuted.append(f"{name}: expected {canon(v['expected'])[:60]} got {canon(got)[:60]}")
        elif "must_not_equal" in v and canon(got) == canon(v["must_not_equal"]):   # presence, not truthiness
            refuted.append(f"{name}: reproduced the forbidden value {canon(v['must_not_equal'])[:60]}")
    notes = (f"; also MISSING_RESULT {missing[:5]}" if missing else "") + (f"; also EXTRA_RESULT {extra[:5]}" if extra else "")
    if refuted:   # a witnessed expected-value contradiction is determinate, whatever else went wrong
        return Result(label, False, "SUITE",
                      f"{len(refuted)}/{len(vectors)} vector(s) did not reproduce: {refuted[0]}{notes}")
    if missing:
        return Result(label, False, "REPORT_CONTRACT",
                      f"MISSING_RESULT: {len(missing)}/{len(vectors)} declared vector(s) not in the report: {missing[:5]}"
                      + (f"; also EXTRA_RESULT {extra[:5]}" if extra else ""))
    if extra:
        return Result(label, False, "REPORT_CONTRACT", f"EXTRA_RESULT: undeclared result(s) {extra[:5]}")
    return Result(label, True, "SUITE", f"{len(vectors)}/{len(vectors)} reproduced (runner-graded reporter)")


def load_declared_uncovered() -> dict[str, str]:
    """Directories explicitly declared as not-run, with reasons. See conformance/uncovered.json."""
    f = CONFORMANCE / "uncovered.json"
    if not f.is_file():
        return {}
    try:
        data = json.loads(f.read_text())
    except Exception as e:
        print(f"conformance/uncovered.json is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(2)
    return ({e["suite"]: e.get("reason", "") for e in data.get("uncovered", [])},
            {e["suite"] for e in data.get("undeclared_vectors", [])},
            {e["suite"]: e.get("reason", "") for e in data.get("requires_live", [])
             if not _live_exclusion_overdue(e)})


def _live_exclusion_overdue(e: dict, today: str | None = None) -> bool:
    """A requires_live exclusion carries owner / reviewed_at / review_after (ISO dates; pipavlo82 on #52: live exclusions
    must age visibly, not become permanent unaudited state). Past review_after it no longer excuses the suite: the suite
    is RUN (and, being non-hermetic, is expected to report NOT COVERED / RUNNER) until someone re-reviews and re-dates it."""
    import datetime as _dt
    ra = e.get("review_after")
    if not ra:
        return False
    # Parse, don't compare strings (zexoverz on #55): as a string, "2026-9-1" sorts after every real date and "never" after
    # every digit, so either would excuse the suite forever. A review_after that is not a real ISO date is treated as
    # overdue, the same fail-closed reading #53 applies to an unparseable date.
    try:
        due = _dt.date.fromisoformat(ra) if isinstance(ra, str) and len(ra) == 10 else None
    except ValueError:
        due = None
    if due is None:
        return True
    return due < _dt.date.fromisoformat(today or _dt.date.today().isoformat())


def apply_overdue(results: list, overdue: list[str]) -> None:
    """An EXPIRED requires_live exclusion is its own deterministic failure (pipavlo82 on #55): the suite still runs for diagnostic
    value, and a live call that happens to pass -- or one that could not run at all -- must not satisfy the re-review obligation.
    But expiry is a lifecycle failure, not a refutation: a result that is ALREADY determinate (SUITE/DRIFT, a vector that actually
    failed to reproduce or a pinned digest that actually drifted) keeps that outcome and exit 1 (zexoverz on #55) -- rewriting it to
    NOT COVERED would soften an independently-verified break down to exit 2's "could not check", the opposite of repository
    precedence. Only PASS and non-determinate results are rewritten to NOT COVERED -> exit 2 (UNVERIFIABLE)."""
    for r in results:
        base = r.name.split("/")[0]
        # a PASS carries kind "SUITE" too (run_suite returns Result(label, True, "SUITE", ...)): keep only DETERMINATE *failures*
        if base in overdue and (r.ok or r.kind not in DETERMINATE):
            outcome = "PASS" if r.ok else r.kind
            r.ok, r.kind = False, "NOT COVERED"
            r.detail = (f"requires_live exclusion EXPIRED (past review_after) -- re-review and re-date it in conformance/uncovered.json; "
                        f"this run's suite outcome was {outcome} (diagnostic only)")


def live_exclusion_lifecycle(today: str | None = None) -> tuple[list[str], list[str]]:
    """(undated, overdue) requires_live suite names, for the report."""
    f = CONFORMANCE / "uncovered.json"
    try:
        data = json.loads(f.read_text())
    except Exception:
        return [], []
    live = data.get("requires_live", [])
    undated = [e["suite"] for e in live if not (e.get("reviewed_at") and e.get("review_after"))]
    overdue = [e["suite"] for e in live if _live_exclusion_overdue(e, today)]
    return undated, overdue


def undeclared_json_files(d) -> list[str]:
    """Names of *.json in a suite dir that the suite.json declares no path for.

    Declared paths are vectors.path, every checks[].vectors.path, AND spec.path — the
    spec/schema is normative material this suite pins by digest, not an unrun vector file.
    Returns [] when there is no suite.json, it is unreadable, or it declares no paths at
    all (an empty declared set would flag every .json, which is a different condition).
    """
    man = d / "suite.json"
    if not man.is_file():
        return []
    try:
        mm = json.loads(man.read_text())
    except Exception:
        return []
    declared_paths = set()
    v = mm.get("vectors")
    if isinstance(v, dict) and v.get("path"):
        declared_paths.add(v["path"])
    for c in (mm.get("checks") or []):
        cv = c.get("vectors")
        if isinstance(cv, dict) and cv.get("path"):
            declared_paths.add(cv["path"])
    sp = mm.get("spec")
    if isinstance(sp, dict) and sp.get("path"):
        declared_paths.add(sp["path"])
    if not declared_paths:
        return []
    return sorted(p.name for p in d.glob("*.json")
                  if p.name not in ({"suite.json"} | declared_paths))


EXEC_EXT = (".py", ".mjs", ".cjs", ".js", ".ts")


def unpinned_executables(d) -> list[str]:
    """Files a suite's adapter / check commands EXECUTE that no declared pin covers.

    A declared pin (checker, mutation_checker, dependencies[], implementations[], vectors, spec -- each a
    {path, sha256}) is enforced; a file that is executed but never declared cannot drift detectably at all,
    so every declared pin can be valid while the code that decides PASS/FAIL changes silently
    (trustless-ai/recompute-kit#53 review, pipavlo82). Paths are resolved relative to the suite dir; only
    tokens that name an existing file with an executable extension count. Report-only by default; set
    RECOMPUTE_STRICT_EXEC_PINS=1 to make each suite with an unpinned executable NOT COVERED.

    SCOPE (stated so it is not read as more, pipavlo82 on #54): this is DIRECT command-executable closure only -- the files a
    command line names (`python gate.py`, `node ref.mjs`). It does NOT establish transitive closure: modules those files
    import, `python -m package.module` targets, and anything loaded at run time are out of scope and never reported here.
    An empty result means "every file a command names is pinned", not "the executed code surface is pinned".
    """
    import os
    import re
    man = d / "suite.json"
    if not man.is_file():
        return []
    try:
        m = json.loads(man.read_text())
    except Exception:
        return []
    units = [m] + [c for c in (m.get("checks") or []) if isinstance(c, dict)]
    executed, pinned = set(), set()
    for u in units:
        cmd = (u.get("adapter") or {}).get("cmd") or ""
        for tok in re.findall(r"[\w./-]+", cmd):
            if tok.endswith(EXEC_EXT) and (d / tok).is_file():
                executed.add(os.path.normpath(tok))
        entries = [u.get(k) for k in ("checker", "mutation_checker", "vectors", "spec")]
        entries += list(u.get("dependencies") or []) + list(u.get("implementations") or [])
        for e in entries:
            if isinstance(e, dict) and e.get("path") and e.get("sha256"):
                pinned.add(os.path.normpath(e["path"]))
    return sorted(executed - pinned)


def main() -> int:
    if not CONFORMANCE.is_dir():
        print(f"no conformance/ directory at {CONFORMANCE}", file=sys.stderr)
        return 2

    dirs = sorted(p for p in CONFORMANCE.iterdir() if p.is_dir())
    if not dirs:
        print("conformance/ contains no suite directories — refusing to report success", file=sys.stderr)
        return 2

    declared, declared_undeclared_vectors, requires_live = load_declared_uncovered()
    import os
    strict_exec = os.environ.get("RECOMPUTE_STRICT_EXEC_PINS") == "1"
    unpinned_exec = [(d.name, u) for d in dirs if d.name not in requires_live for u in [unpinned_executables(d)] if u]
    results = []
    for d in dirs:
        if d.name in requires_live:
            # skipped, never run — and reported as such, never folded into the pass count
            results.append(Result(d.name, False, "REQUIRES LIVE", "needs external binary / live service — not hermetic"))
            continue
        results.extend(run_suite(d))

    if strict_exec:
        for n, files in unpinned_exec:
            results.append(Result(f"{n}/exec-pins", False, "NOT COVERED",
                                  f"executes files no declared pin covers: {', '.join(files)}"))

    # Separate axis from pass/fail: a suite.json declares ONE vectors file, so any other
    # .json beside it is executed by nothing. The suite still runs — dropping it would
    # trade one blind spot for a bigger one — but a green line for a suite whose other
    # five vector files never ran is false coverage, so it gets its own report.
    undeclared: list[tuple[str, list[str]]] = []
    for d in dirs:
        others = undeclared_json_files(d)
        if others:
            undeclared.append((d.name, others))

    # A declared-uncovered suite is still printed and still counted as not-run. It just
    # does not fail the build, because someone signed their name to it being unrun.
    stale = []
    for r in results:
        if r.kind == "UNDECLARED" and r.name in declared_undeclared_vectors:
            r.kind = "DECLARED UNCOVERED"
            continue
        if r.name in declared:
            if r.kind == "NOT COVERED":
                r.kind = "DECLARED UNCOVERED"
            else:
                stale.append(r.name)

    # an EXPIRED requires_live exclusion is a deterministic NOT COVERED whatever the suite did (before any status/exit is computed)
    apply_overdue(results, live_exclusion_lifecycle()[1])

    width = max(len(r.name) for r in results)
    for r in results:
        status = {
            "NOT COVERED": "NOT COVERED",
            "DECLARED UNCOVERED": "NOT RUN",
            "REQUIRES LIVE": "SKIPPED",
            "UNVERIFIABLE": "UNVERIFIABLE",
            "REPORT_CONTRACT": "REPORT CONTRACT",
        }.get(r.kind, "FAIL") if not r.ok else "PASS"
        print(f"{status:<12} {r.name:<{width}}  {r.detail}")

    passed = [r for r in results if r.ok]
    not_run = [r for r in results if r.kind == "DECLARED UNCOVERED"]
    live = [r for r in results if r.kind == "REQUIRES LIVE"]
    failed = [r for r in results if not r.ok and r.kind not in ("DECLARED UNCOVERED", "REQUIRES LIVE")]

    print()
    print(f"{len(passed)}/{len(results)} suites passed")
    if not_run:
        # never collapse this into the pass line — that is the ambiguity the repo exists to remove
        print(f"{len(not_run)}/{len(results)} declared NOT RUN (conformance/uncovered.json) — unrun, not passing:")
        for r in not_run:
            print(f"    - {r.name}")

    undeclared_undisclosed = [(n, f) for n, f in undeclared if n not in declared_undeclared_vectors]
    # An exclusion that outlives the thing it excused is worse than none: it under-reports
    # coverage while looking deliberate. Once a suite declares its vectors, its entry here
    # is a false claim that they are unrun.
    stale_undeclared = sorted(declared_undeclared_vectors - {n for n, _ in undeclared})
    if undeclared:
        print()
        print("vector files present that NO manifest declares (executed by nothing):")
        for n, files in undeclared:
            mark = "  " if n in declared_undeclared_vectors else "! "
            print(f"  {mark}{n}: {', '.join(files)}")
        if undeclared_undisclosed:
            print("  (! = not listed in conformance/uncovered.json — add it or declare the vectors)")

    if unpinned_exec and not strict_exec:
        print()
        print(f"executed files that NO declared pin covers ({len(unpinned_exec)} suites) -- a change to these cannot")
        print("surface as DRIFT; report-only (RECOMPUTE_STRICT_EXEC_PINS=1 makes each one NOT COVERED):")
        for n, files in unpinned_exec:
            print(f"    - {n}: {', '.join(files)}")
    live_undated, live_overdue = live_exclusion_lifecycle()
    if live_undated or live_overdue:
        print()
        if live_overdue:
            print("requires_live exclusions PAST review_after -- no longer excused, run as normal suites (re-review and re-date them):")
            for n in live_overdue:
                print(f"    - {n}")
        if live_undated:
            print("requires_live exclusions with no reviewed_at/review_after -- they age invisibly (add both):")
            for n in live_undated:
                print(f"    - {n}")

    if live:
        print(f"{len(live)}/{len(results)} SKIPPED as non-hermetic (conformance/uncovered.json requires_live) — not passing:")
        for r in live:
            print(f"    - {r.name}")

    if stale_undeclared:
        print()
        print("conformance/uncovered.json: undeclared_vectors entries now declared — remove them:")
        for n in stale_undeclared:
            print(f"    - {n}")
        return 1

    if stale:
        print()
        print("conformance/uncovered.json is stale — these now run and must be removed from it:")
        for n in stale:
            print(f"    - {n}")
        return 1

    if undeclared_undisclosed:
        return 2  # vector files nobody runs: could not check, not a refutation

    if failed:
        print()
        print("not green, by cause:")
        for kind in ("SUITE", "DRIFT", "UNDECLARED", "REPORT_CONTRACT", "UNVERIFIABLE", "RUNNER", "NOT COVERED"):
            group = [r for r in failed if r.kind == kind]
            if not group:
                continue
            label = {
                "SUITE": "suite failed (a vector did not reproduce)",
                "DRIFT": "pinned digest mismatch (vectors/spec changed without repinning)",
                "UNVERIFIABLE": "gate ran and could not conclude (its own exit 2: nothing checked, nothing refuted)",
                "REPORT_CONTRACT": "reporter did not complete the reporter contract (missing/extra/invalid/empty report, "
                                   "nonzero reporter exit, invalid corpus) -- the implementation under test, not the environment",
                "RUNNER": "runner could not execute it (environment, not evidence)",
                "UNDECLARED": "vector files present that no manifest declares — unrun, and green without them is false coverage",
            "NOT COVERED": "discovered but never run — treat as failing, not as absent",
            }[kind]
            print(f"  {label}:")
            for r in group:
                print(f"    - {r.name}: {r.detail}")

        shown = {"SUITE", "DRIFT", "UNDECLARED", "REPORT_CONTRACT", "UNVERIFIABLE", "RUNNER", "NOT COVERED"}
        for r in [r for r in failed if r.kind not in shown]:   # no failing result may be diagnostically invisible
            print(f"  {r.kind}: {r.name}: {r.detail}")

        exit_code = exit_code_for_failures(failed)
        if exit_code == 1:
            print("\nexit 1 — verified-bad (something ran and refuted)")
            return 1
        print("\nexit 2 — UNVERIFIABLE (nothing refuted; something could not be run)")
        return exit_code

    return 0


if __name__ == "__main__":
    sys.exit(main())
