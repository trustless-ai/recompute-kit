#!/usr/bin/env python3
"""check_real_record — makes ONE landed serializer binding record load-bearing in CI, distinct
from binding-record.vectors.json's fifteen synthetic shape cases.

Real gap this closes (Pavlo, PR #26 review): suite.json only ever pinned/ran the synthetic shape
vectors. records/tsei.frozen-artifact.json validated once via a manual verdict() call at land time,
but nothing in the suite would have reddened if it silently drifted afterward — an "immutable"
record with no mechanical check behind its immutability is just a claim.

This script is the adapter for a SECOND, separately named check in suite.json (the same "checks"
array pattern pq-key-binding-v0 already uses). Two things make drift visible, not one:

  1. The runner itself pins the record's exact SHA-256 in the check's own `vectors.sha256` and
     reds with DRIFT before this script ever runs if the bytes changed at all -- byte-level, catches
     even a change that would still validate structurally (e.g. a materially different but
     schema-conformant edit).
  2. THIS script re-confirms the record still validates structurally against the frozen schema, by
     calling validate_binding_record.py's own verdict() function directly -- the same function a
     human invoked once by hand at land time, now run every CI pass instead of trusted from memory.

Reads the record on stdin (kind:"stdio" feeds the check's declared vectors.path there), matching
every other adapter in this directory. Exit 0 the record still validates, 1 it does not (a
determinate SUITE failure), 2 the checker itself could not run (e.g. malformed input JSON -- a
fault in this checker, never silently read as a pass).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from validate_binding_record import verdict, ValidatorFault  # noqa: E402


def main() -> int:
    try:
        record = json.loads(sys.stdin.read())
    except Exception as e:
        print(f"FAULT could not parse record from stdin as JSON: {e}")
        return 2

    try:
        result = verdict(record)
    except ValidatorFault as f:
        print(f"FAULT schema construct this checker does not implement -> VALIDATOR_FAULT:{f}")
        return 2

    if result == "valid":
        print("OK tsei.frozen-artifact -> valid")
        return 0

    print(f"BAD tsei.frozen-artifact -> {result} (want valid)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
