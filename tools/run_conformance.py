#!/usr/bin/env python3
"""Run every conformance suite exactly as its own suite.json declares.

The suite manifest is the contract, so this reads it rather than assuming:

    adapter.cmd     the command, run with the suite directory as cwd
    adapter.kind    "stdio" -> the vectors file is fed on STDIN
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

import hashlib
import json
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
UNDETERMINED = {"RUNNER", "NOT COVERED", "UNDECLARED"}


class Result:
    def __init__(self, name: str, ok: bool, kind: str, detail: str):
        self.name, self.ok, self.kind, self.detail = name, ok, kind, detail


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
        if sf.is_file():
            actual = sha256(sf)
            if actual != spec["sha256"]:
                return Result(label, False, "DRIFT",
                              f"{spec['path']} sha256 {actual[:16]}… != pinned {spec['sha256'][:16]}…")

    if kind and kind != "stdio":
        return Result(label, False, "NOT COVERED", f"adapter.kind '{kind}' not implemented by this runner")

    stdin_data = b""
    if vec_path:
        stdin_data = (d / vec_path).read_bytes()

    try:
        proc = subprocess.run(cmd, shell=True, cwd=d, input=stdin_data,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    except subprocess.TimeoutExpired:
        return Result(label, False, "RUNNER", "timed out after 300s")
    except Exception as e:
        return Result(label, False, "RUNNER", f"could not execute adapter.cmd: {e}")

    out = proc.stdout.decode("utf-8", "replace").strip()
    lines = [l for l in out.splitlines() if l.strip()]
    # A crashing runtime prints its own banner last ("Bun v1.3.14 (Linux x64)"), which says
    # nothing about why. Report the diagnostic line, not the footer.
    noise = ("Bun v", "at ", "^", "|")
    signal = [l for l in lines if not l.lstrip().startswith(noise)]
    last = (signal[-1] if signal else (lines[-1] if lines else "(no output)"))[:110]

    if proc.returncode == 127:
        return Result(label, False, "RUNNER", f"command not found (127) — interpreter missing, not a suite failure: {cmd}")
    if proc.returncode != 0:
        # A dependency that will not resolve is an environment failure. Calling it a refuted
        # vector would be a check reporting confidently about the wrong question.
        env_markers = ("Cannot find module", "Cannot find package", "ModuleNotFound",
                       "ImportError", "No module named", "command not found", "ENOENT")
        if any(m in out for m in env_markers):
            return Result(label, False, "RUNNER", f"environment, not evidence: {last}")
        return Result(label, False, "SUITE", f"exit {proc.returncode}: {last}")
    return Result(label, True, "SUITE", last)


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
            {e["suite"]: e.get("reason", "") for e in data.get("requires_live", [])})


def main() -> int:
    if not CONFORMANCE.is_dir():
        print(f"no conformance/ directory at {CONFORMANCE}", file=sys.stderr)
        return 2

    dirs = sorted(p for p in CONFORMANCE.iterdir() if p.is_dir())
    if not dirs:
        print("conformance/ contains no suite directories — refusing to report success", file=sys.stderr)
        return 2

    declared, declared_undeclared_vectors, requires_live = load_declared_uncovered()
    results = []
    for d in dirs:
        if d.name in requires_live:
            # skipped, never run — and reported as such, never folded into the pass count
            results.append(Result(d.name, False, "REQUIRES LIVE", "needs external binary / live service — not hermetic"))
            continue
        results.extend(run_suite(d))

    # Separate axis from pass/fail: a suite.json declares ONE vectors file, so any other
    # .json beside it is executed by nothing. The suite still runs — dropping it would
    # trade one blind spot for a bigger one — but a green line for a suite whose other
    # five vector files never ran is false coverage, so it gets its own report.
    undeclared: list[tuple[str, list[str]]] = []
    for d in dirs:
        man = d / "suite.json"
        if not man.is_file():
            continue
        try:
            mm = json.loads(man.read_text())
        except Exception:
            continue
        # every path the manifest declares, singular form or checks array
        declared_paths = set()
        v = mm.get("vectors")
        if isinstance(v, dict) and v.get("path"):
            declared_paths.add(v["path"])
        for c in (mm.get("checks") or []):
            cv = c.get("vectors")
            if isinstance(cv, dict) and cv.get("path"):
                declared_paths.add(cv["path"])
        if not declared_paths:
            continue
        others = sorted(p.name for p in d.glob("*.json")
                        if p.name not in ({"suite.json"} | declared_paths))
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

    width = max(len(r.name) for r in results)
    for r in results:
        status = {
            "NOT COVERED": "NOT COVERED",
            "DECLARED UNCOVERED": "NOT RUN",
            "REQUIRES LIVE": "SKIPPED",
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
        for kind in ("SUITE", "DRIFT", "UNDECLARED", "RUNNER", "NOT COVERED"):
            group = [r for r in failed if r.kind == kind]
            if not group:
                continue
            label = {
                "SUITE": "suite failed (a vector did not reproduce)",
                "DRIFT": "pinned digest mismatch (vectors/spec changed without repinning)",
                "RUNNER": "runner could not execute it (environment, not evidence)",
                "UNDECLARED": "vector files present that no manifest declares — unrun, and green without them is false coverage",
            "NOT COVERED": "discovered but never run — treat as failing, not as absent",
            }[kind]
            print(f"  {label}:")
            for r in group:
                print(f"    - {r.name}: {r.detail}")

        determinate = [r for r in failed if r.kind in DETERMINATE]
        if determinate:
            print("\nexit 1 — verified-bad (something ran and refuted)")
            return 1
        print("\nexit 2 — UNVERIFIABLE (nothing refuted; something could not be run)")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
