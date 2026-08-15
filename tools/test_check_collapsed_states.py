#!/usr/bin/env python3
"""Controls for the collapsed-state checker.

The point of this suite is the FAIL path. A checker that has only ever been run against
clean code has not been shown to work — it has been shown to be silent, which is what a
broken one also looks like. So the first control drives it to a determinate finding, and
asserts the EXACT exit code rather than "non-zero": this repo's convention distinguishes
1 (verified-bad) from 2 (unverifiable), and a control that accepts either would pass while
the tool collapsed those two states — the very defect under test.

Run: python3 tools/test_check_collapsed_states.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_collapsed_states.py"
FIXTURES = ROOT / "tools" / "fixtures" / "collapsed"

EXIT_GOOD, EXIT_BAD, EXIT_UNVERIFIABLE, EXIT_USAGE = 0, 1, 2, 64

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECKER), *args],
                          capture_output=True, text=True, timeout=120)


def negative_control_it_can_fail() -> None:
    print("\nNEGATIVE CONTROL — two real causes, one marker (must be CAUGHT):")
    r = run(str(FIXTURES / "two_causes_collapsed.py"))
    check("exit is exactly 1 (verified-bad), not merely non-zero",
          r.returncode == EXIT_BAD, f"got {r.returncode}")
    check("names the collapsed marker", "review_unavailable" in r.stdout, r.stdout[:160])
    check("reports it as COLLAPSED", "COLLAPSED MARKERS" in r.stdout)
    check("points at both producing sites", r.stdout.count("NO REASON") >= 2, r.stdout[:300])
    check("does not exit 2 — it COULD check, and the answer was bad",
          r.returncode != EXIT_UNVERIFIABLE)


def positive_control_it_can_pass() -> None:
    print("\nPOSITIVE CONTROL — same two causes, reason field added (must PASS):")
    r = run(str(FIXTURES / "two_causes_reasoned.py"))
    check("exit is exactly 0 (verified-good)", r.returncode == EXIT_GOOD,
          f"got {r.returncode}: {r.stdout[:200]}")
    check("says so plainly", "no collapsed markers found" in r.stdout)


def discriminates_rather_than_flagging_the_shape() -> None:
    print("\nDISCRIMINATION — the two fixtures differ only by the reason field:")
    bad = run(str(FIXTURES / "two_causes_collapsed.py")).returncode
    good = run(str(FIXTURES / "two_causes_reasoned.py")).returncode
    check("the checker separates them", bad == EXIT_BAD and good == EXIT_GOOD,
          f"collapsed={bad} reasoned={good}")


def second_axis_inert_data_is_not_a_state() -> None:
    """Regression: v1 flagged sample documents in a self-test as a collapsed marker.

    The original controls varied only the reason axis and passed while the tool was wrong
    on this one. Found against real code (cross-reference-console reference/projection.py),
    not imagined.
    """
    print("\nSECOND AXIS — same marker twice, never emitted (must NOT be reported):")
    r = run(str(FIXTURES / "inert_fixture_data.py"))
    check("exit is exactly 0 — inert data is not a state",
          r.returncode == EXIT_GOOD, f"got {r.returncode}: {r.stdout[:220]}")
    check("does not name the marker", "'reject'" not in r.stdout, r.stdout[:200])


def unverifiable_is_its_own_verdict() -> None:
    print("\nUNVERIFIABLE — nothing analysable (must be 2, never 0):")
    r = run(str(FIXTURES / "does_not_exist_anywhere.py"))
    check("exit is exactly 2 (unverifiable)", r.returncode == EXIT_UNVERIFIABLE,
          f"got {r.returncode}")
    check("could-not-check never reports as a pass", r.returncode != EXIT_GOOD)

    print("\n  and a non-Python input is NOT COVERED, not passed:")
    r2 = run(str(ROOT / "README.md"))
    check("non-Python alone yields 2, not 0", r2.returncode == EXIT_UNVERIFIABLE,
          f"got {r2.returncode}")


def main() -> int:
    if not CHECKER.exists():
        print(f"checker not found at {CHECKER}", file=sys.stderr)
        return EXIT_UNVERIFIABLE
    print("controls for check_collapsed_states.py")
    negative_control_it_can_fail()
    positive_control_it_can_pass()
    discriminates_rather_than_flagging_the_shape()
    second_axis_inert_data_is_not_a_state()
    unverifiable_is_its_own_verdict()
    print()
    if failures:
        print(f"{len(failures)} control(s) failed:")
        for f in failures:
            print(f"    - {f}")
        return EXIT_BAD
    print("all controls passed — the checker can fail, can pass, and tells them apart")
    return EXIT_GOOD


if __name__ == "__main__":
    sys.exit(main())
