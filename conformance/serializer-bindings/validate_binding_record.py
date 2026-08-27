#!/usr/bin/env python3
"""serializer binding record — conformance validator.

Reads the FROZEN schema (binding-record.schema.json) and enforces it DIRECTLY — the schema is the
primary artifact, so structural validity is recomputed from it rather than re-encoding its rules by
hand (a hand-copy would silently drift from the shape it claims to check). A small draft-07 subset is
implemented: exactly the constructs this schema uses — type (object/string/integer), required,
additionalProperties:false, properties, $ref to #/definitions, pattern, minLength, minimum, const.
const uses JSON equality (same JSON type AND value), so a boolean const is NOT satisfied by the number 1.
The implemented keyword set is EXPLICIT (SUPPORTED_KEYWORDS) and the WHOLE schema is preflighted once
against it before any record is checked (_preflight_schema), so a keyword outside it — e.g. adding
maxLength, even inside an unused definition or an absent optional property — is a VALIDATOR FAULT
surfaced distinctly (exit 2), never silently ignored. "Couldn't check" is its own verdict; an
unimplemented construct can never turn into a false pass, regardless of which record exercised it.

On top of structure it enforces the ONE cross-field semantic JSON Schema alone cannot express:

    producer_conformance.qualification.vectors  MUST be the same immutable pre-image as
    serializer_contract.vectors

"passes the pinned vectors" is only evidence if they are THIS contract's vectors; an implementation
qualified against some other vector set has not been qualified against this contract.

Each vector case is {case_id, record, expected_verdict}. The validator recomputes a verdict token and
compares. Negative controls (records that MUST be rejected, each pinned to its exact rejection token)
are representative critical-rule controls: at least one negative per implemented rule class — type,
required, additionalProperties, pattern, minLength, minimum, const (including the boolean-vs-number
distinction), and the cross-field vectors-identity rule — so disabling any one guard reds the suite.
They are not an exhaustive per-property enumeration. Exit 0 when all reproduce, 1 on any determinate mismatch, 2 if the checker
itself could not run a case. Pure stdlib — no jsonschema import, so a missing dependency can never
turn this suite into a false green.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = json.load(open(HERE / "binding-record.schema.json"))


class ValidatorFault(Exception):
    """The schema used a construct this subset does not implement — a fault in the checker, not a
    verdict about the record. Kept distinct so 'could not check' never masquerades as 'valid'."""


# The draft-07 keyword subset this validator implements. ANY schema keyword outside this set is a
# VALIDATOR FAULT (see _check_keywords), never silently ignored — so adding e.g. maxLength to the
# schema surfaces as unverifiable rather than a false pass. ($schema/$id/title/description/definitions
# are structural or documentation and assert nothing per-node.)
SUPPORTED_KEYWORDS = {
    "$schema", "$id", "title", "description", "definitions",
    "type", "required", "additionalProperties", "properties", "$ref",
    "pattern", "minLength", "minimum", "const",
}


def _check_keywords(node):
    for k in node:
        if k not in SUPPORTED_KEYWORDS:
            raise ValidatorFault(f"unsupported schema keyword '{k}' — not in the implemented subset")


def _preflight_schema(node, where="<root>"):
    """Walk the ENTIRE schema ONCE, up front, and fault on any keyword outside SUPPORTED_KEYWORDS —
    including inside unused definitions and optional properties that no test record happens to reach.
    This is what makes "any unsupported construct is a validator fault" a property of the schema rather
    than of whichever record exercised it. Recurses through properties and definitions; a $ref node is
    checked for stray siblings but its target is reached via the definitions walk (so no cycles)."""
    if "$ref" in node:
        for k in node:
            if k not in ("$ref", "description"):
                raise ValidatorFault(f"unsupported keyword beside $ref at {where}: '{k}'")
        return
    _check_keywords(node)
    for name, sub in node.get("properties", {}).items():
        _preflight_schema(sub, _join(where if where != "<root>" else "", name))
    for name, sub in node.get("definitions", {}).items():
        _preflight_schema(sub, f"#/definitions/{name}")


def _json_type(v):
    """JSON's own type of a Python value. bool is tested BEFORE int deliberately: in Python bool is a
    subclass of int (True == 1, False == 0), but JSON boolean true is NOT JSON number 1. Conflating
    them is exactly the const-equality bug this guards."""
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if v is None:
        return "null"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "unknown"


def _json_equal(a, b):
    """draft-07 const equality is JSON equality: same JSON type AND equal value. Python's bare ==
    would accept 1 == True and 0 == False; JSON does not, so a boolean const is not satisfied by 1."""
    return _json_type(a) == _json_type(b) and a == b


def _resolve(node, root):
    """A property schema may be a local $ref (optionally alongside a description). The referent is
    authoritative for validation; the sibling description is documentation only."""
    if "$ref" in node:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValidatorFault(f"unsupported $ref target: {ref}")
        cur = root
        for part in ref[2:].split("/"):
            cur = cur[part]
        return cur
    return node


def _validate(node, value, path, root):
    """Return the FIRST violation token in a deterministic walk (required in declared order, then
    properties in schema order), or None if valid. Deterministic order makes each expected verdict
    a single stable token."""
    # Keyword-inventory enforcement is NOT here: a per-record walk only reaches the nodes THIS record
    # exercises, so an unsupported keyword in an unused definition or an absent optional property would
    # slip through. The whole schema is preflighted once (see _preflight_schema), so the "any
    # unsupported keyword is a fault" guarantee is a property of the schema, not of the record.
    s = _resolve(node, root)
    t = s.get("type")

    if t == "object":
        if not isinstance(value, dict):
            return f"type:{path or '<root>'}"
        props = s.get("properties", {})
        for req in s.get("required", []):                       # missing-required first
            if req not in value:
                return f"missing:{_join(path, req)}"
        if s.get("additionalProperties", True) is False:        # then unexpected keys
            for k in value:
                if k not in props:
                    return f"additional:{_join(path, k)}"
        for k, sub in props.items():                            # then descend, schema order
            if k in value:
                err = _validate(sub, value[k], _join(path, k), root)
                if err:
                    return err
        return None

    if t == "string":
        if not isinstance(value, str):
            return f"type:{path}"
        if "minLength" in s and len(value) < s["minLength"]:
            return f"minLength:{path}"
        if "pattern" in s and re.match(s["pattern"], value) is None:
            return f"pattern:{path}"
        return None

    if t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"type:{path}"
        if "minimum" in s and value < s["minimum"]:
            return f"minimum:{path}"
        return None

    if "const" in s:
        return None if _json_equal(value, s["const"]) else f"const:{path}"

    raise ValidatorFault(f"unhandled schema construct at {path or '<root>'}")


def _join(path, key):
    return f"{path}.{key}" if path else key


def verdict(record):
    """A single stable token: 'valid', a structural token (missing:/additional:/type:/pattern:/
    minLength:/minimum:/const: <path>), or the cross-field semantic token."""
    err = _validate(SCHEMA, record, "", SCHEMA)
    if err:
        return err
    # Structure guaranteed present now, so these lookups are safe. The one thing the schema cannot say:
    # the vectors the producer passed ARE the contract's vectors — same immutable pre-image, field for field.
    if (record["producer_conformance"]["qualification"]["vectors"]
            != record["serializer_contract"]["vectors"]):
        return "qualification_vectors_ne_contract_vectors"
    return "valid"


def main(argv):
    # Preflight the whole schema ONCE before any record: an unimplemented keyword anywhere in the
    # schema (even in an unused definition) makes the entire suite unverifiable, not silently green.
    try:
        _preflight_schema(SCHEMA)
    except ValidatorFault as f:
        print(f"FAULT schema preflight -> VALIDATOR_FAULT:{f}")
        print(f"\nschema uses a construct this checker does not implement — VALIDATOR FAULT (unverifiable)")
        return 2

    path = argv[1] if len(argv) > 1 else "binding-record.vectors.json"
    fx = json.load(open(path))
    cases = fx["cases"]
    fails = faults = 0
    for c in cases:
        want = c["expected_verdict"]
        try:
            got = verdict(c["record"])
            fault = False
        except ValidatorFault as f:
            got, fault = f"VALIDATOR_FAULT:{f}", True
        ok = (not fault) and got == want
        faults += fault
        fails += (not ok) and (not fault)
        tag = "FAULT" if fault else ("OK " if ok else "BAD")
        print(f"{tag} {c['case_id']:<44} -> {got:<48} (want {want})")
    n = len(cases)
    if faults:
        print(f"\n{faults}/{n} cases could not be checked — VALIDATOR FAULT (unverifiable)")
        return 2
    print(f"\n{n - fails}/{n} cases reproduced" + ("" if not fails else "  <- MISMATCH"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
