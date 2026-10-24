"""Research-only DEILS reveal reporter. No production authorization or grading."""
import hashlib
import json
import re
import secrets
import sys

import rfc8785

PRIVACY = "research.deils-privacy-blinding.v0"
LEGACY = "research.deils-legacy-integer-replay.v0"
SAFE = 9007199254740991


def fresh_blinding():
    """Issuer-side research example. Verification alone cannot prove entropy/freshness."""
    return secrets.token_bytes(32).hex()


def content_parse(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("duplicate member")
            obj[key] = value
        return obj

    def no_float(token):
        raise ValueError("outside integer-token research domain")

    value = json.loads(raw, object_pairs_hook=pairs, parse_float=no_float,
                       parse_constant=no_float)

    def admit(v):
        if isinstance(v, str):
            v.encode("utf-8", "strict")
        elif type(v) is int:
            if not -SAFE <= v <= SAFE:
                raise ValueError("unsafe integer")
        elif isinstance(v, list):
            for x in v:
                admit(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                admit(k)
                admit(x)
        elif v is not None and type(v) is not bool:
            raise ValueError("unsupported type")
    admit(value)
    return value


def result(status, state=None, reason=None, stage="validation", canonical=None):
    return {"status": status, "state": state, "reason": reason, "stage": stage,
            "hash_evaluated": canonical is not None,
            "canonical_utf8_hex": None if canonical is None else canonical.hex(),
            "recomputed_commitment": None if canonical is None else
            "sha256:" + hashlib.sha256(canonical).hexdigest()}


def verify(inp):
    profile = inp.get("profile")
    if profile not in (PRIVACY, LEGACY):
        return result("UNVERIFIABLE", reason="RESEARCH_PROFILE_UNSUPPORTED", stage="admission")
    if inp.get("disclosed") is False:
        return result("UNVERIFIABLE", "content_withheld", stage="disclosure")
    try:
        content = content_parse(inp["content_json"])
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        return result("UNVERIFIABLE", reason="RESEARCH_CONTENT_INVALID", stage="admission")
    if content is None and profile == LEGACY:
        return result("UNVERIFIABLE", "content_withheld", stage="disclosure")
    if profile == PRIVACY:
        if not isinstance(content, dict):
            return result("UNVERIFIABLE", reason="RESEARCH_CONTENT_OBJECT_REQUIRED")
        if "blinding" not in content:  # GUARD_REQUIRED
            return result("UNVERIFIABLE", reason="RESEARCH_REQUIRED_BLINDING_ABSENT")
        if "blinding" in content:
            b = content["blinding"]
            if not (isinstance(b, str) and re.fullmatch(r"[0-9a-f]{64}", b)):  # GUARD_FORMAT
                return result("UNVERIFIABLE", reason="blinding_malformed")
    if inp.get("content_schema", "json-integers") == "gps-integers-research.v0":
        bounds = {"latE7": (-900000000, 900000000),
                  "lonE7": (-1800000000, 1800000000), "accuracyCm": (0, SAFE)}
        if not isinstance(content, dict) or any(
            type(content.get(k)) is not int or not lo <= content[k] <= hi
            for k, (lo, hi) in bounds.items()
        ):
            return result("UNVERIFIABLE", reason="RESEARCH_GPS_RANGE_OR_TYPE")
    elif inp.get("content_schema", "json-integers") != "json-integers":
        return result("UNVERIFIABLE", reason="RESEARCH_SCHEMA_UNSUPPORTED")
    if not isinstance(inp.get("commitment"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", inp["commitment"]):
        return result("UNVERIFIABLE", reason="malformed_commitment")
    preimage = content  # GUARD_PREIMAGE
    canonical = rfc8785.dumps(preimage)
    computed = "sha256:" + hashlib.sha256(canonical).hexdigest()
    equal = computed == inp["commitment"]  # GUARD_COMPARE
    return result("VERIFIED" if equal else "REFUTED",
                  "content_bound" if equal else "content_commitment_mismatch",
                  stage="commitment", canonical=canonical)


def report(document):
    vectors = document["vectors"]
    if not isinstance(vectors, list) or not vectors:
        raise ValueError("ZERO_CASES or invalid corpus")
    names = [v["name"] for v in vectors]
    if any(not isinstance(n, str) or not n for n in names) or len(names) != len(set(names)):
        raise ValueError("invalid/duplicate case identity")
    return {v["name"]: verify(v["input"]) for v in vectors}


if __name__ == "__main__":
    try:
        output = report(json.load(sys.stdin))
        sys.stdout.buffer.write((json.dumps(output, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=True) + "\n").encode("ascii"))
    except (ValueError, KeyError, TypeError) as error:
        print("REPORT_INPUT_UNGRADABLE: " + str(error), file=sys.stderr)
        sys.exit(2)
