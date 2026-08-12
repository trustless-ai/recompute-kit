#!/usr/bin/env python3
"""
pq_key_binding.v1 — temporal authority reference resolver.

The one thing this file exists to make impossible: a stored value reaching a verdict.

v0 said an epoch-0 binding governs [T0, Trot) and never defined T0. Implementations
filled it from local state, which made the temporal boundary verdict-bearing while
staying out of the JCS statement — so it never reached the content address, the
leaf, or any anchored root. The same committed statement, same leaf and same
anchored root could then produce a different verdict, and no root recomputation
could detect the change.

Here governs_from is DERIVED:

    R1  key_epoch 0        -> 0
    R2  key_epoch n>0      -> anchored_at of the EARLIEST anchored batch whose
                              leaves contain the binding's cc
    R3  key_epoch n>0 with no containing anchor -> None; never in force
    R4  among bindings with governs_from <= artifact anchor_time, not revoked at or
        before it, the greatest governs_from governs
    R5  submitted_at is informational and MUST NOT be read here

submitted_at is deliberately never referenced below. That absence is the point of
the profile, so it is asserted rather than merely intended: see
`test_submitted_at_unused` and the source scan in run().

Run:  python3 temporal_resolve.py [pq-key-binding-v1.temporal-vectors.json]
      exit 0 if every case reproduces, 1 otherwise.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / "pq-key-binding-v1.temporal-vectors.json"


def governs_from(binding, anchors):
    """R1-R3. Returns the temporal authority boundary, or None if the binding has none."""
    if binding["key_epoch"] == 0:
        return 0  # R1 — the baseline key governs from creation, not from its anchor
    containing = [a for a in anchors if binding["cc"] in a["leaves"]]
    if not containing:
        return None  # R3 — cannot be proven, therefore cannot govern
    return min(a["anchored_at"] for a in containing)  # R2 — EARLIEST, never latest


def resolve_in_force(bindings, anchors, at_time):
    """R4. Which binding governs an artifact anchored at `at_time`."""
    eligible = []
    for b in bindings:
        gf = governs_from(b, anchors)
        if gf is None:
            continue
        if gf > at_time:
            continue
        rev = b.get("revoked_at")
        if rev is not None and at_time >= rev:
            continue
        eligible.append((gf, b))
    if not eligible:
        return None, None, "no_in_force_binding"
    gf, b = max(eligible, key=lambda pair: pair[0])
    return b, gf, "resolved_at_anchor_time"


def test_submitted_at_unused():
    """R5, enforced against source rather than trusted.

    A comment promising not to read a field is not a control. If a future edit
    reintroduces submitted_at into the resolution path, this fails loudly.

    Scoped to the two functions that actually decide verdicts. A first version
    scanned the whole file and flagged its own detector lines — a check reporting
    a problem it had itself created, which is the same shape of error the rest of
    this suite exists to catch, so it is worth leaving recorded rather than
    quietly fixing.
    """
    src = Path(__file__).read_text()
    targets = []
    for name in ("governs_from", "resolve_in_force"):
        m = re.search(rf"^def {name}\(.*?(?=^def |\Z)", src, flags=re.S | re.M)
        if m:
            targets.append((name, m.group(0)))
    if len(targets) != 2:
        return False, ["could not locate both resolution functions to scan"]

    hits = []
    for name, body in targets:
        body = re.sub(r'""".*?"""', "", body, flags=re.S)          # drop docstrings
        for ln in body.splitlines():
            if ln.lstrip().startswith("#"):
                continue                                            # drop comments
            if "submitted_at" in ln:
                hits.append(f"{name}: {ln.strip()}")
    return (not hits), hits


def run(path):
    fx = json.loads(Path(path).read_text())
    anchors = fx["anchors"]
    fails = 0

    # Per-binding derivation, checked against the value each vector states.
    for b in fx["bindings"]:
        got = governs_from(b, anchors)
        want = b["expected_governs_from"]
        ok = got == want
        if not ok:
            fails += 1
        print(f"{'ok  ' if ok else 'FAIL'} governs_from({b['name']}) = {got}  (expected {want})")

    # Cases.
    for c in fx["cases"]:
        bindings = [dict(b) for b in fx["bindings"]]
        mut = c.get("mutate")
        if mut:
            for b in bindings:
                if b["name"] == mut["binding"]:
                    b[mut["field"]] = mut["to"]
        b, gf, reason = resolve_in_force(bindings, anchors, c["artifact"]["anchor_time"])
        got = {
            "resolved": b["name"] if b else None,
            "governs_from": gf,
            "resolution_reason": reason,
        }
        want = {k: c["expected"][k] for k in ("resolved", "governs_from", "resolution_reason")}
        ok = got == want
        if not ok:
            fails += 1
        print(f"{'ok  ' if ok else 'FAIL'} {c['name']:<45} {got if not ok else ''}")
        if not ok:
            print(f"       expected {want}")

    unused, hits = test_submitted_at_unused()
    if not unused:
        fails += 1
    print(f"{'ok  ' if unused else 'FAIL'} submitted_at absent from the resolution path")
    for h in hits:
        print(f"       reads it: {h.strip()}")

    total = len(fx["bindings"]) + len(fx["cases"]) + 1
    print(f"\n{total - fails}/{total} checks reproduced")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
