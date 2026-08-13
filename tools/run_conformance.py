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

Exit 0 only when every discovered suite ran and passed.
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


class Result:
    def __init__(self, name: str, ok: bool, kind: str, detail: str):
        self.name, self.ok, self.kind, self.detail = name, ok, kind, detail


def run_suite(d: pathlib.Path) -> Result:
    manifest = d / "suite.json"
    if not manifest.is_file():
        return Result(d.name, False, "NOT COVERED", "no suite.json — nothing declares how to run this")

    try:
        m = json.loads(manifest.read_text())
    except Exception as e:
        return Result(d.name, False, "RUNNER", f"suite.json is not valid JSON: {e}")

    adapter = m.get("adapter") or {}
    cmd = adapter.get("cmd")
    kind = adapter.get("kind", "")
    if not cmd:
        return Result(d.name, False, "NOT COVERED", "suite.json declares no adapter.cmd")

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
                return Result(d.name, False, "NOT COVERED", f"vectors declared but missing: {vec_path}")
            if pinned:
                actual = sha256(vf)
                if actual != pinned:
                    return Result(d.name, False, "DRIFT",
                                  f"{vec_path} sha256 {actual[:16]}… != pinned {pinned[:16]}…")

    spec = m.get("spec")
    if isinstance(spec, dict) and spec.get("path") and spec.get("sha256"):
        sf = d / spec["path"]
        if sf.is_file():
            actual = sha256(sf)
            if actual != spec["sha256"]:
                return Result(d.name, False, "DRIFT",
                              f"{spec['path']} sha256 {actual[:16]}… != pinned {spec['sha256'][:16]}…")

    if kind and kind != "stdio":
        return Result(d.name, False, "NOT COVERED", f"adapter.kind '{kind}' not implemented by this runner")

    stdin_data = b""
    if vec_path:
        stdin_data = (d / vec_path).read_bytes()

    try:
        proc = subprocess.run(cmd, shell=True, cwd=d, input=stdin_data,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    except subprocess.TimeoutExpired:
        return Result(d.name, False, "RUNNER", "timed out after 300s")
    except Exception as e:
        return Result(d.name, False, "RUNNER", f"could not execute adapter.cmd: {e}")

    out = proc.stdout.decode("utf-8", "replace").strip()
    tail = [l for l in out.splitlines() if l.strip()]
    last = tail[-1][:100] if tail else "(no output)"

    if proc.returncode == 127:
        return Result(d.name, False, "RUNNER", f"command not found (127) — interpreter missing, not a suite failure: {cmd}")
    if proc.returncode != 0:
        return Result(d.name, False, "SUITE", f"exit {proc.returncode}: {last}")
    return Result(d.name, True, "SUITE", last)


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
            {e["suite"] for e in data.get("undeclared_vectors", [])})


def main() -> int:
    if not CONFORMANCE.is_dir():
        print(f"no conformance/ directory at {CONFORMANCE}", file=sys.stderr)
        return 2

    dirs = sorted(p for p in CONFORMANCE.iterdir() if p.is_dir())
    if not dirs:
        print("conformance/ contains no suite directories — refusing to report success", file=sys.stderr)
        return 2

    declared, declared_undeclared_vectors = load_declared_uncovered()
    results = [run_suite(d) for d in dirs]

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
            vp = ((json.loads(man.read_text()).get("vectors") or {}) or {}).get("path")
        except Exception:
            continue
        if not vp:
            continue
        others = sorted(p.name for p in d.glob("*.json") if p.name not in {"suite.json", vp})
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
        }.get(r.kind, "FAIL") if not r.ok else "PASS"
        print(f"{status:<12} {r.name:<{width}}  {r.detail}")

    passed = [r for r in results if r.ok]
    not_run = [r for r in results if r.kind == "DECLARED UNCOVERED"]
    failed = [r for r in results if not r.ok and r.kind != "DECLARED UNCOVERED"]

    print()
    print(f"{len(passed)}/{len(results)} suites passed")
    if not_run:
        # never collapse this into the pass line — that is the ambiguity the repo exists to remove
        print(f"{len(not_run)}/{len(results)} declared NOT RUN (conformance/uncovered.json) — unrun, not passing:")
        for r in not_run:
            print(f"    - {r.name}")

    undeclared_undisclosed = [(n, f) for n, f in undeclared if n not in declared_undeclared_vectors]
    if undeclared:
        print()
        print("vector files present that NO manifest declares (executed by nothing):")
        for n, files in undeclared:
            mark = "  " if n in declared_undeclared_vectors else "! "
            print(f"  {mark}{n}: {', '.join(files)}")
        if undeclared_undisclosed:
            print("  (! = not listed in conformance/uncovered.json — add it or declare the vectors)")

    if stale:
        print()
        print("conformance/uncovered.json is stale — these now run and must be removed from it:")
        for n in stale:
            print(f"    - {n}")
        return 1

    if undeclared_undisclosed:
        return 1

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
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
