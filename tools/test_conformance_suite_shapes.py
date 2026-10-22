#!/usr/bin/env python3
"""bin/conformance-suite must REFUSE the manifest shapes it does not implement, not traceback.

The tool implements one shape: a single-check suite whose `adapter.contract` is `reporter`. It used
to read `man["vectors"]["path"]` unconditionally and join `spec.path` to the suite directory
unconditionally, so 15 of 30 manifests on main died with an uncaught exception — and an uncaught
exception exits **1**.

Exit 1 is this repo's code for "a vector was refuted". "I cannot read this declaration" is not a
refutation, and the difference is not cosmetic: mcp/server.py maps the exit code through
`_verdict()`, where 1 becomes `verified-bad` with gate `deny`. So pointing the MCP conformance tool
at any multi-check suite returned an affirmative "this candidate is non-conformant" on no evidence
at all. (#72)

So the properties here are: never a traceback, and never exit 1 for a declaration this tool cannot
read. Includes a removal control, because a test that cannot fail is the thing this repo exists to
detect.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "bin" / "conformance-suite"
CONFORMANCE = ROOT / "conformance"
# single-check + reporter: the one shape the tool implements, so the positive control
GRADES = "dex-calldata-v0"
# multi-check, and both of its checks are reporter, so --check must make it gradeable
MULTI, MULTI_CHECK = "erc8275-win-rate-bps-v0", "conformance"
# single-check but self_grading: refused on the declaration, before the adapter runs
SELF_GRADING = "captured-admission-v0"
# single-check whose spec is a CROSS-REPO reference with no sha256 — joining it to the suite
# directory raised FileNotFoundError on a file that was never meant to be local
UNPINNED_SPEC = "pq-key-binding-v1-profile"

fails = []


def tool_traceback(out: str) -> bool:
    """True only if a traceback in `out` has a frame inside bin/conformance-suite."""
    return any(line.lstrip().startswith('File "') and str(TOOL) in line
               for line in out.splitlines())


def run(*args, tool=TOOL, cwd=ROOT):
    p = subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True,
                       cwd=cwd, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return p.returncode, p.stdout + p.stderr


def check(name, cond, detail=""):
    if not cond:
        fails.append(f"{name}: {detail}")


# ── the universal properties, over every manifest in the repo ────────────────────────────────────
# A sweep, not a list of the shapes we happen to know about: a manifest added tomorrow is covered.
suites = sorted(p.parent for p in CONFORMANCE.glob("*/suite.json"))
check("sweep found manifests", len(suites) >= 10, f"only found {len(suites)}")
for d in suites:
    rc, out = run("--suite", str(d.relative_to(ROOT)))
    # Only a traceback raised *in the tool* is the tool's failure. fail_closed relays the adapter's
    # stderr, so on a box missing a suite's declared python_modules the adapter's own ImportError
    # traceback appears here while the tool correctly exits 2 — that is the environment, not this tool.
    check(f"no traceback for {d.name}", not tool_traceback(out), out[-400:])
    if "cannot grade this suite" in out:
        check(f"{d.name} refusal exits 2, not 1", rc == 2,
              f"a declaration it cannot read must be could-not-run (2), got {rc}")
        check(f"{d.name} refusal says it graded nothing", "nothing was graded" in out, out[-300:])

# ── positive control: the shape it DOES implement still grades ───────────────────────────────────
rc, out = run("--suite", f"conformance/{GRADES}")
check("positive control exits 0", rc == 0, f"exit {rc}\n{out[-400:]}")
check("positive control is conformant", "CONFORMANT" in out, out[-300:])
check("positive control reports a count", "reproduced" in out, out[-300:])

# ── multi-check: refused without --check, gradeable with it ──────────────────────────────────────
rc, out = run("--suite", f"conformance/{MULTI}")
check("multi-check refused", rc == 2, f"exit {rc}")
check("multi-check names its checks", MULTI_CHECK in out, out[-300:])
check("multi-check points at the general runner", "run_conformance.py" in out, out[-300:])

rc, out = run("--suite", f"conformance/{MULTI}", "--check", MULTI_CHECK)
check("--check grades a multi-check reporter suite", rc == 0, f"exit {rc}\n{out[-500:]}")
check("--check result is conformant", "CONFORMANT" in out, out[-300:])

rc, out = run("--suite", f"conformance/{MULTI}", "--check", "no-such-check")
check("unknown --check refused", rc == 2, f"exit {rc}")
check("unknown --check lists the real ones", MULTI_CHECK in out, out[-300:])

rc, out = run("--suite", f"conformance/{GRADES}", "--check", "anything")
check("--check on a single-check manifest refused", rc == 2, f"exit {rc}")

# ── contract: refused from the DECLARATION, before the adapter runs ──────────────────────────────
rc, out = run("--suite", f"conformance/{SELF_GRADING}")
check("self_grading refused", rc == 2, f"exit {rc}")
check("self_grading names the contract", "self_grading" in out, out[-400:])
# The old code ran the adapter and then failed to parse its human summary as JSON. If the adapter
# ran, its own output is in ours — that is how we know the refusal came first.
check("self_grading adapter did NOT run", "cases reproduced" not in out,
      "the adapter ran before the contract was checked; its summary is in the output:\n" + out[-400:])
check("self_grading does not blame the output shape", "was not JSON" not in out, out[-300:])

# ── an unpinned / cross-repo spec is a reference, not a local file ───────────────────────────────
# The real suite that exposed this (pq-key-binding-v1-profile) is ALSO self_grading, so the contract
# refusal fires before the spec is ever read and masks the question entirely -- the first version of
# this test asserted "no FileNotFoundError" there and passed for that reason, not because the spec
# handling was right. So isolate it: a reporter suite whose spec is a cross-repo reference with no
# sha256, pointing at a path that does not exist locally and was never meant to.
def write_suite(d, *, spec=None, cases_key="vectors", adapter="echo '{\"a\":{\"x\":1}}'"):
    d.mkdir(parents=True, exist_ok=True)
    (d / "vectors.json").write_text(
        json.dumps({cases_key: [{"name": "a", "expected": {"x": 1}}]}) + "\n")
    man = {"profile": d.name, "vectors": {"path": "vectors.json"},
           "adapter": {"kind": "stdio", "cmd": adapter, "contract": "reporter"}}
    if spec is not None:
        man["spec"] = spec
    (d / "suite.json").write_text(json.dumps(man) + "\n")
    return d


with tempfile.TemporaryDirectory() as tmp:
    # control that the synthetic suite grades at all, or the next assertion means nothing
    base = write_suite(Path(tmp) / "xrepo-baseline-v0")
    rc, out = run("--suite", str(base), cwd=tmp)
    check("synthetic reporter suite grades", rc == 0, f"exit {rc}\n{out[-400:]}")

    d = write_suite(Path(tmp) / "xrepo-spec-v0",
                    spec={"repo": "trustless-ai/elsewhere", "path": "spec/not-local.md", "pr": 1})
    rc, out = run("--suite", str(d), cwd=tmp)
    check("cross-repo spec: no FileNotFoundError", "FileNotFoundError" not in out, out[-400:])
    check("cross-repo spec: still grades", rc == 0, f"exit {rc}\n{out[-400:]}")
    check("cross-repo spec: says it is not verified here", "not a pin" in out, out[-400:])

# the real suite must at least not traceback, whatever refuses it first
rc, out = run("--suite", f"conformance/{UNPINNED_SPEC}")
check("unpinned-spec suite does not traceback", "Traceback" not in out, out[-400:])
check("unpinned-spec suite refused cleanly", rc == 2, f"exit {rc}")

# ── zero vectors must not certify conformance ────────────────────────────────────────────────────
# Synthesised: no manifest on main reaches this today, because every `cases`-keyed corpus happens to
# be self_grading and is refused earlier. Accidental safety is not a guard.
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp) / "zero-vectors-v0"
    d.mkdir()
    (d / "vectors.json").write_text(json.dumps({"cases": [{"name": "a", "expected": {}}]}) + "\n")
    # The adapter must emit VALID JSON, or the run reds on parsing and the empty corpus is never
    # the reason -- which is how the first version of this assertion passed with the guard removed.
    (d / "suite.json").write_text(json.dumps({
        "profile": "zero-vectors-v0",
        "vectors": {"path": "vectors.json"},
        "adapter": {"kind": "stdio", "cmd": "echo '{}'", "contract": "reporter"},
    }) + "\n")
    rc, out = run("--suite", str(d), cwd=tmp)
    check("a corpus the tool reads as empty must not pass", rc != 0,
          f"0 vectors reported CONFORMANT with exit {rc}\n{out[-400:]}")
    check("empty corpus is could-not-run", rc == 2, f"exit {rc}")
    check("empty corpus says why", "no vectors" in out, out[-300:])

# ── REMOVAL CONTROL ──────────────────────────────────────────────────────────────────────────────
# Put the unconditional read back and the traceback + exit 1 must return, or none of the above is
# evidence that the guards are what is holding this up.
with tempfile.TemporaryDirectory() as tmp:
    broken = Path(tmp) / "conformance-suite"
    source = TOOL.read_text(encoding="utf-8")
    anchor = "        checks = man.get(\"checks\")\n"
    if source.count(anchor) != 1:
        fails.append("REMOVAL CONTROL: anchor not found exactly once in bin/conformance-suite "
                     f"({source.count(anchor)} occurrences) — the control did not apply, so it "
                     "proves nothing")
    else:
        broken.write_text(source.replace(
            anchor, anchor + "        man[\"vectors\"]  # removal control: the old unconditional read\n", 1),
            encoding="utf-8")
        rc, out = run("--suite", f"conformance/{MULTI}", tool=broken)
        check("REMOVAL CONTROL restores the traceback", "Traceback" in out,
              "reinstating the unconditional read did not reproduce the failure; the guard above "
              f"may be passing for another reason\n{out[-400:]}")
        check("REMOVAL CONTROL restores exit 1", rc == 1,
              f"expected the old KeyError exit 1, got {rc}")

if fails:
    print(f"FAIL — bin/conformance-suite manifest shapes ({len(fails)})")
    for f in fails:
        print("  - " + f.replace("\n", "\n    "))
    raise SystemExit(1)
print(f"OK — refuses every shape it cannot read across {len(suites)} manifests: no traceback, "
      "never exit 1, adapter not run before the contract is checked, and the removal control bites")
