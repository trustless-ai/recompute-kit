#!/usr/bin/env python3
"""Grade erc8275-win-rate-bps.v0 vectors.

Input: the complete vector artifact on stdin.
Output: {vector.name: recomputed integer}.

The gate derives the convention hash from the artifact's convention_spec and
requires every vector to pin that exact hash. Unknown/missing pointers fail
closed instead of being interpreted under a current default.
"""

import hashlib
import json
import sys
from copy import deepcopy


BPS_HASH = "0x0501b75db8e9ef4ef67c74efcfbe2a200b0a7e5aea5ca62f778c91c119e68daf"


def jcs_flat_string_map(value: dict[str, str]) -> bytes:
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError("convention_spec must be a string-to-string object")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def convention_hash(spec: dict[str, str]) -> str:
    return "0x" + hashlib.sha256(jcs_flat_string_map(spec)).hexdigest()


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def compute(wins: int, losses: int) -> int:
    if not is_int(wins) or not is_int(losses) or wins < 0 or losses < 0:
        raise ValueError("wins and losses must be non-negative integers")
    total = wins + losses
    if total == 0:
        raise ValueError("zero total is outside the computable domain")
    return (wins * 20000 + total) // (2 * total)


def grade(fixture: dict, legacy_float: bool = False) -> dict[str, object]:
    derived = convention_hash(fixture.get("convention_spec"))
    if derived != BPS_HASH:
        raise ValueError(f"convention hash drift: {derived}")

    results: dict[str, object] = {}
    for vector in fixture.get("vectors", []):
        if vector.get("governing_convention_hash") != derived:
            results[vector["name"]] = {
                "status": "unverifiable",
                "reason": "unknown_or_missing_governing_convention_hash",
            }
            continue
        inputs = vector["inputs"]
        wins = inputs["commit_gated_wins"]
        losses = inputs["commit_gated_losses"]
        if legacy_float:
            results[vector["name"]] = round(wins / (wins + losses), 4)
        else:
            results[vector["name"]] = compute(wins, losses)
    return results


def prove_mutations(fixture: dict) -> dict[str, object]:
    """Return the expected map only if every guard is demonstrably load-bearing."""
    correct = grade(fixture)
    legacy = grade(fixture, legacy_float=True)
    vectors = fixture.get("vectors", [])
    legacy_killed = any(
        type(legacy[v["name"]]) is not int or legacy[v["name"]] != v["expected"]
        for v in vectors
    )

    results: dict[str, object] = {}
    for vector in vectors:
        name = vector["name"]
        unknown = deepcopy(fixture)
        unknown["vectors"] = [deepcopy(vector)]
        unknown["vectors"][0]["governing_convention_hash"] = "0x" + "00" * 32
        missing = deepcopy(fixture)
        missing["vectors"] = [deepcopy(vector)]
        del missing["vectors"][0]["governing_convention_hash"]
        unknown_result = grade(unknown)[name]
        missing_result = grade(missing)[name]
        guards_hold = (
            type(correct[name]) is int
            and correct[name] == vector["expected"]
            and legacy_killed
            and unknown_result
            == {
                "status": "unverifiable",
                "reason": "unknown_or_missing_governing_convention_hash",
            }
            and missing_result == unknown_result
        )
        results[name] = vector["expected"] if guards_hold else "__MUTATION_SURVIVED__"
    return results


def main() -> int:
    fixture = json.load(sys.stdin)
    if "--prove-mutations" in sys.argv:
        results = prove_mutations(fixture)
    else:
        results = grade(fixture, legacy_float="--legacy-float" in sys.argv)
    print(json.dumps(results, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
