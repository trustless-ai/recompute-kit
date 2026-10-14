#!/usr/bin/env python3
"""Controls for the stale-bytecode vector's cache PRECONDITION.

The `stale-bytecode` vector proves per-run isolation: without it, CPython revalidates a timestamp
.pyc on (mtime, size), both of which the fixture holds constant, so a stale cache makes the run
misread its mutants. That control only means something where a .pyc is actually written. Where none
is, the vector reproduces its expected result trivially and `check.py` prints CONFORMANT having
established nothing — a control that cannot fail, reporting success.

So the vector declares `requires_bytecode_cache`, and `check.py` must MEASURE the premise before
accepting the result, reporting NORUN / UNVERIFIABLE / exit 2 when it is absent.

Measuring it is where this gets subtle, and the controls below exist because of two distinct ways to
get it wrong, each found by a different reviewer:

  - babyblueviper1 (#71): PYTHONDONTWRITEBYTECODE in the CALLER's environment removes the premise.
    `check.py` strips it, so the vector keeps RUNNING where bytecode is merely disabled by the
    variable — a false NORUN there would switch the gate off for no reason.
  - pipavlo82 (#70): the first probe measured `sys.executable`, but the fixtures invoke `python3`
    through PATH. A `python3` that is a different interpreter, or the same one wrapped with -B,
    gives a probe that reports a cache the fixture never gets. The probe must observe the artifact
    the premise is about: the vector's own test command, in the vector's own fixture.

CONTROL 3 is the removal control for the second: revert the probe to `sys.executable` and the false
CONFORMANT comes back. Everything runs against a throwaway copy; the repo tree is never modified.
"""
import os, pathlib, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = "conformance/mutation-survival-v0"
VECTOR = "stale-bytecode"


def stage():
    tmp = tempfile.mkdtemp(prefix="cache-precondition-control-")
    os.makedirs(os.path.join(tmp, "bin"))
    shutil.copy2(os.path.join(ROOT, "bin", "recompute-mutation-survival"),
                 os.path.join(tmp, "bin", "recompute-mutation-survival"))
    shutil.copytree(os.path.join(ROOT, SUITE), os.path.join(tmp, SUITE),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return tmp


def wrapper_dir(tmp):
    """A `python3` earlier on PATH that is this interpreter plus -B. Interpreter identity is held
    constant on purpose: the only variable is that the fixture's `python3` writes no bytecode."""
    d = os.path.join(tmp, "wrapbin")
    os.makedirs(d, exist_ok=True)
    p = pathlib.Path(d, "python3")
    p.write_text(f'#!/bin/sh\nexec {sys.executable} -B "$@"\n')
    p.chmod(0o755)
    return d


def run(tmp, env_extra=None, path_prefix=None):
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    if env_extra:
        env.update(env_extra)
    if path_prefix:
        env["PATH"] = path_prefix + os.pathsep + env["PATH"]
    p = subprocess.run([sys.executable, "check.py"], capture_output=True, text=True,
                       cwd=os.path.join(tmp, SUITE), env=env)
    return p.returncode, p.stdout + p.stderr


def norun(out):
    return any(line.startswith("NORUN") and VECTOR in line for line in out.splitlines())


fails = []

# POSITIVE — as shipped, the premise holds and the vector runs.
tmp = stage()
try:
    rc, out = run(tmp)
    if rc != 0:
        fails.append(f"POSITIVE: check.py should pass as shipped, got exit {rc}\n{out}")
    if norun(out):
        fails.append(f"POSITIVE: {VECTOR} should RUN here, got NORUN\n{out}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# CONTROL 1 — the variable alone must NOT stop the vector (babyblueviper1). check.py strips it.
tmp = stage()
try:
    rc, out = run(tmp, env_extra={"PYTHONDONTWRITEBYTECODE": "1"})
    if rc != 0:
        fails.append(f"CONTROL 1: the variable is stripped, so check.py should still pass, got exit {rc}\n{out}")
    if norun(out):
        fails.append(f"CONTROL 1: {VECTOR} must still RUN under PYTHONDONTWRITEBYTECODE=1\n{out}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# CONTROL 2 — a `python3` on PATH that writes no bytecode must be REFUSED, not passed (pipavlo82).
tmp = stage()
try:
    rc, out = run(tmp, path_prefix=wrapper_dir(tmp))
    if not norun(out):
        fails.append("CONTROL 2: a PATH `python3` that writes no .pyc must report NORUN for "
                     f"{VECTOR}, not accept its result\n{out}")
    if rc != 2:
        fails.append(f"CONTROL 2: an unestablished premise is could-not-run (exit 2), got exit {rc}\n{out}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# CONTROL 3 — REMOVAL. Probe `sys.executable` instead of the fixture's own command and the vacuous
# CONFORMANT returns, which is what makes the binding in CONTROL 2 load-bearing rather than decorative.
tmp = stage()
try:
    chk = pathlib.Path(tmp, SUITE, "check.py")
    src = chk.read_text()
    anchor = "subprocess.run(tc, cwd=w, shell=True, capture_output=True, env=env)"
    if src.count(anchor) != 1:
        fails.append(f"CONTROL 3: probe anchor not found exactly once in check.py "
                     f"({src.count(anchor)} occurrences) — the removal control did not apply, "
                     "so it proves nothing")
    else:
        chk.write_text(src.replace(
            anchor,
            'subprocess.run([sys.executable, "-c", "import sys"], cwd=w, capture_output=True, env=env)\n'
            '        pathlib.Path(w, "__pycache__").mkdir(exist_ok=True)\n'
            '        pathlib.Path(w, "__pycache__", "probe.pyc").write_bytes(b"\\x00")', 1))
        rc, out = run(tmp, path_prefix=wrapper_dir(tmp))
        if rc == 2 or norun(out):
            fails.append("CONTROL 3: reverting the probe to sys.executable should restore the false "
                         f"CONFORMANT, but it still refused (exit {rc}) — CONTROL 2 may be passing "
                         f"for some other reason\n{out}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    print("FAIL — cache-precondition controls")
    for f in fails:
        print("  - " + f.replace("\n", "\n    "))
    raise SystemExit(1)
print("OK — cache precondition: positive, env-strip, PATH-wrapper refusal, and removal control")
