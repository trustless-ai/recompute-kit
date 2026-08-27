#!/usr/bin/env python3
"""serializer binding record — conformance validator.

Reads the FROZEN schema (binding-record.schema.json) and enforces it DIRECTLY — the schema is the
primary artifact, so structural validity is recomputed from it rather than re-encoding its rules by
hand (a hand-copy would silently drift from the shape it claims to check). A small draft-07 subset is
implemented: exactly the constructs this schema uses — type (object/string/integer), required,
additionalProperties:false, properties, $ref to #/definitions, pattern, minLength, minimum, const.
A schema construct this subset does not implement is a VALIDATOR FAULT, surfaced distinctly (exit 2),
never silently treated as a pass — "couldn't check" is its own verdict.

On top of structure it enforces the ONE cross-field semantic JSON Schema alone cannot express:

    producer_conformance.qualification.vectors  MUST be the same immutable pre-image as
    serializer_contract.vectors

"passes the pinned vectors" is only evidence if they are THIS contract's vectors; an implementation
qualified against some other vector set has not been qualified against this contract.

Each vector case is {case_id, record, expected_verdict}. The validator recomputes a verdict token and
compares. Negative controls (records that MUST be rejected, each pinned to its exact rejection token)
prove every rule can fail. Exit 0 when all reproduce, 1 on any determinate mismatch, 2 if the checker
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
        return None if value == s["const"] else f"const:{path}"

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
