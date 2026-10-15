#!/usr/bin/env python3
"""Every test in tools/ must be invoked by a workflow, and every invocation must exist.

A test that CI never runs has no failure mode — the conformance workflow says so in its own
comments. The gap is not hypothetical: on 2026-10-15 three PRs each appended one line to the same
`run:` block in `.github/workflows/conformance.yml` (#52, #82, #83, with #80 adding a step just
below). Merging the first put the other two into conflict, and the resolution is to keep every
line. Keeping all but one is a one-character-looking mistake that passes review green, because the
dropped test simply never runs and nothing is red.

So the relation is checked in BOTH directions:

  exists -> wired    a tracked tools/test_*.py that no workflow invokes
  wired  -> exists   an invocation naming a file that is not there (a rename, a typo, a deletion)

⚠ The mechanism has a premise: that tests are invoked by LITERAL path. If someone starts running
them through pytest, `unittest discover`, or a shell loop over a glob, scanning for
`tools/test_*.py` tokens would silently under-report and this guard would pass while covering
nothing. So the premise is asserted too — an unrecognised invocation style makes this test FAIL
rather than quietly measure the wrong thing.

⚠ Known limit, stated rather than papered over: this cannot detect its OWN line being dropped. If
the workflow stops invoking this file, this file does not run, and nothing complains. The hole
shrinks from every test in tools/ to exactly one, and that one is this comment.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# A tracked tools/test_*.py that deliberately must NOT be wired. Empty, and meant to stay empty:
# a test nobody runs is the thing this file exists to find, so an exemption has to be argued for
# in writing rather than left as an omission.
NOT_WIRED: set[str] = set()

# Invocation styles that would make path-scanning unsound. Matching any of these is a refusal:
# the guard cannot establish its relation, so it must not report success.
UNSOUND = (
    (re.compile(r"\bpytest\b"), "pytest collects by discovery, not by literal path"),
    (re.compile(r"unittest\s+discover"), "unittest discover collects by pattern"),
    (re.compile(r"for\s+\w+\s+in\s+.*tools/test_"), "a shell loop over a glob hides which tests run"),
    (re.compile(r"tools/test_\*"), "a glob hides which tests run"),
)

TEST_PATH = re.compile(r"tools/test_[A-Za-z0-9_]+\.py")


def tracked_tests():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "tools/test_*.py"],
                         capture_output=True, text=True, check=True).stdout.split()
    return set(out)


def workflow_text():
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    return {f.name: f.read_text(encoding="utf-8") for f in files}


fails = []
texts = workflow_text()
if not texts:
    fails.append("no workflow files found — the sweep is broken, and a sweep that finds nothing "
                 "proves nothing")

# 0. the premise: path-scanning only measures anything if tests are invoked by literal path
for name, text in texts.items():
    for pattern, why in UNSOUND:
        if pattern.search(text):
            fails.append(f"{name}: unrecognised invocation style ({why}). Scanning for literal "
                         "tools/test_*.py paths would under-report, so this guard cannot "
                         "conclude — teach it the new style instead of letting it pass.")

exists = tracked_tests()
if len(exists) < 5:
    fails.append(f"only {len(exists)} tracked tools/test_*.py found — git ls-files is not "
                 "returning the test files, so neither direction below means anything")

wired = {}
for name, text in texts.items():
    for path in TEST_PATH.findall(text):
        wired.setdefault(path, set()).add(name)

# 1. exists -> wired
unwired = sorted(exists - set(wired) - NOT_WIRED)
if unwired:
    fails.append("tracked but invoked by NO workflow: " + ", ".join(unwired) +
                 ". A test CI never runs has no failure mode. Wire it, or declare it in "
                 "NOT_WIRED with a reason.")

# 2. wired -> exists
dangling = sorted(p for p in wired if p not in exists)
if dangling:
    fails.append("invoked by a workflow but not tracked: " +
                 ", ".join(f"{p} (in {', '.join(sorted(wired[p]))})" for p in dangling) +
                 ". A renamed or deleted test leaves CI running a path that is not there.")

# 3. a NOT_WIRED entry must still be a real file, or the exemption is stale
stale = sorted(NOT_WIRED - exists)
if stale:
    fails.append("declared in NOT_WIRED but not tracked: " + ", ".join(stale))

if fails:
    print(f"FAIL — wired tests ({len(fails)})")
    for f in fails:
        print("  - " + f)
    raise SystemExit(1)
print(f"OK — {len(exists)} test(s) in tools/, each invoked by a workflow; "
      f"{len(wired)} invocation(s), each resolving to a tracked file")
for p in sorted(exists):
    print(f"  {p}  <- {', '.join(sorted(wired[p]))}")
