#!/usr/bin/env python3
"""Controls for conformance/mutation-survival-v0/self-check.

The self-check proves the suite's vectors are load-bearing against the primitive's own guards. That
claim is only worth something if the self-check itself can fail — a self-check that always passes is
precisely the decorative-test failure the primitive exists to detect, one level up.

So: POSITIVE control (the self-check passes as shipped) and NEGATIVE control (remove the vector that
witnesses a guard, and the self-check must report that guard SURVIVED and exit 1). Both run against a
throwaway copy, so the repo tree is never modified.
"""
import json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = "conformance/mutation-survival-v0"
# Dropping this vector removes the only witness for the per-run isolation guard.
VECTOR, GUARD = "stale-bytecode", "per-run isolation removed"

def stage():
    tmp = tempfile.mkdtemp(prefix="self-check-control-")
    os.makedirs(os.path.join(tmp, "bin"))
    shutil.copy2(os.path.join(ROOT, "bin", "recompute-mutation-survival"),
                 os.path.join(tmp, "bin", "recompute-mutation-survival"))
    shutil.copytree(os.path.join(ROOT, SUITE), os.path.join(tmp, SUITE),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return tmp

def run(tmp):
    p = subprocess.run([os.path.join(tmp, SUITE, "self-check")],
                       capture_output=True, text=True, cwd=tmp)
    return p.returncode, p.stdout + p.stderr

fails = []

tmp = stage()
try:
    rc, out = run(tmp)
    if rc != 0:
        fails.append(f"POSITIVE control: self-check should pass as shipped, got exit {rc}\n{out}")
    else:
        print("OK   positive control — self-check passes as shipped, exit 0")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

tmp = stage()
try:
    vp = os.path.join(tmp, SUITE, "mutation-survival-v0.vectors.json")
    d = json.load(open(vp))
    before = len(d["vectors"])
    d["vectors"] = [v for v in d["vectors"] if v["name"] != VECTOR]
    if len(d["vectors"]) != before - 1:
        fails.append(f"NEGATIVE control could not set itself up: vector {VECTOR!r} not found")
    json.dump(d, open(vp, "w"), indent=2)
    rc, out = run(tmp)
    survived = any(GUARD in line and "SURVIVED" in line for line in out.splitlines())
    if rc != 1 or not survived:
        fails.append(f"NEGATIVE control: dropping {VECTOR!r} must leave {GUARD!r} SURVIVED and exit 1; "
                     f"got exit {rc}, survived={survived}\n{out}")
    else:
        print(f"OK   negative control — without {VECTOR!r}, {GUARD!r} SURVIVED, exit 1")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

for f in fails:
    print("FAIL " + f)
print("mutation-survival self-check controls: " + ("OK" if not fails else "BROKEN"))
sys.exit(1 if fails else 0)
