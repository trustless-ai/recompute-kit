"""Owner-side grading bookkeeping; never an oracle for semantic expected values.

Owners declare the expectation shape their comparison actually consumes. A
missing/malformed expectation is ungradable, not a mismatch. Record a result
only after comparison. Exit codes use the existing self_grading contract.
"""
import sys


def expectation_error(case, field, *, kind="object", required=(), types=None):
    if field not in case:
        return f"missing {field}"
    value = case[field]
    if kind == "string":
        return None if isinstance(value, str) else f"{field} must be a string"
    if not isinstance(value, dict) or not value:
        return f"{field} must be a nonempty object"
    for key in required:
        if key not in value:
            return f"missing {field}.{key}"
    for key, shape in (types or {}).items():
        if key not in value:
            continue
        v = value[key]
        if shape == "string":
            valid = isinstance(v, str)
        elif shape == "nullable_string":
            valid = v is None or isinstance(v, str)
        elif shape == "integer":
            valid = type(v) is int  # bool is not a declared integer expectation
        else:
            raise ValueError(f"unsupported expectation shape: {shape}")
        if not valid:
            return f"{field}.{key} must be {shape}"
    return None


class Grading:
    """One established outcome per admitted position; no corpus-length credit."""
    def __init__(self, cases):
        self.cases = list(cases.values()) if isinstance(cases, dict) else cases
        self.names = list(cases) if isinstance(cases, dict) else [
            str(c.get("case_id", c.get("name", c.get("id", i)))) for i, c in enumerate(cases)]
        self.admitted = len(cases)
        self.outcomes = {}
        self.reasons = {}
        self.faults = []

    def ungradable(self, index, reason):
        self._record(index, "ungradable")
        self.reasons[index] = reason
        print(f"UNVERIFIABLE: UNGRADABLE_CASE {self.names[index]}: {reason}", file=sys.stderr)

    def expectation(self, index, case, field, **shape):
        error = expectation_error(case, field, **shape)
        if error is not None:
            self.ungradable(index, error)
            return False
        return True

    def _record(self, index, outcome):
        if index in self.outcomes or not 0 <= index < self.admitted:
            self.faults.append(f"duplicate or out-of-range grading outcome: {index}")
            return
        self.outcomes[index] = outcome

    def record(self, index, reproduced):
        self._record(index, "reproduced" if reproduced else "refuted")

    @property
    def reproduced(self):
        return sum(v == "reproduced" for v in self.outcomes.values())

    @property
    def refuted(self):
        return sum(v == "refuted" for v in self.outcomes.values())

    def finish(self):
        # Keep the final evidence summary last when a runner combines both streams.
        sys.stdout.flush()
        for i in range(self.admitted):
            if i not in self.outcomes:
                self.ungradable(i, "no grading outcome recorded")
        ungradable = sum(v == "ungradable" for v in self.outcomes.values())
        for reason in self.faults:
            print(f"UNVERIFIABLE: GRADING_ACCOUNTING {reason}", file=sys.stderr)
        if ungradable or self.faults:
            print(f"GRADING admitted={self.admitted} graded={self.reproduced + self.refuted} "
                  f"reproduced={self.reproduced} refuted={self.refuted} ungradable={ungradable}", file=sys.stderr)
        # An established refutation stays determinate even alongside absent evidence.
        return 1 if self.refuted else 2 if ungradable or self.faults else 0
