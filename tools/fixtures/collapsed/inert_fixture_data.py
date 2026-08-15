"""CONTROL FOR THE SECOND AXIS — the same marker twice, but never emitted.

The first version of this checker flagged exactly this shape in real code
(cross-reference-console `reference/projection.py`) and was wrong: those were sample
documents inside a self-test, not two branches producing a state. Nobody branches on them
and no caller ever sees them.

That miss is instructive. The original controls varied ONE axis — reason present vs
absent — and passed cleanly while the tool was wrong on a second axis it never varied:
emitted state vs inert data. A control has to match the claim's dimensionality, or it
passes while checking the adjacent thing.

The checker MUST NOT report this file.
"""

VERDICT_REJECT = "reject"

# Lookup/sample data. Identical marker, twice, going nowhere.
SAMPLE_DOCS = [
    {"verdict": VERDICT_REJECT, "artifact": "a" * 8},
    {"verdict": VERDICT_REJECT, "artifact": "b" * 8},
]


def build_expected():
    # Bound to a local, used for comparison, never returned as a state.
    base = {"verdict": VERDICT_REJECT, "note": "expected value for a vector"}
    other = {"verdict": VERDICT_REJECT, "note": "second expected value"}
    return len(base) + len(other)
