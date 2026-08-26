#!/usr/bin/env python3
"""erc-8309.envelope golden-set adapter — recompute-and-compare, recompute-kit contract.

Reads the vectors fixture on STDIN (the grader pipes it in), reads the erc-8309.envelope schema
from the suite dir, and for each vector re-derives the answer from inputs.object:
  - validate the object against the schema;
  - serialize it under the bound serializer RFC 8785 JCS (no trailing byte) -> conforming bytes
    (erc-8309.envelope stays JCS-bound; this is the value that is stored/anchored);
  - compute the COUNTERFACTUAL result under the wrong serializer, encode-json-utf8-lf.v0. Because
    .v0 has a real input domain, that outcome is DISCRIMINATED, not a boolean:
      ENCODED  -> exact bytes_hex, byte_length, sha256, relation_to_jcs (DISTINCT), or
      REJECTED -> the exact .v0 rejection category (e.g. NEGATIVE_ZERO).
    The fourth vector (jcs_number_edges, a JCS-admitted negative zero) proves "different digest" is
    too weak a vocabulary: the wrong serializer can be out-of-domain entirely.

Emits {"results": {name: {conforming_bytes_hex, conforming_jcs_sha256, lf_v0_counterfactual_result}}},
which the grader compares to each vector's `expected`. Nothing here trusts the stored expected values;
they are re-derived and the grader does the comparison.

The .v0 counterfactual encoder here is inline (stdlib domain validation + rfc8785 admitted rendering +
one terminal LF) and is pinned by the leg's contract block to encode-json-utf8-lf.v0 (spec/vectors
SHA-256). Deps: rfc8785 (RFC 8785 JCS), jsonschema.
"""
import json, hashlib, sys, os, struct, math
import rfc8785, jsonschema

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "erc-8309.envelope.schema.json")))

SAFE_MAX = 9007199254740991
NEG_ZERO_BITS = 0x8000000000000000

def sha(b): return hashlib.sha256(b).hexdigest()
def jcs(o): return rfc8785.dumps(o)

class _V0Reject(Exception):
    def __init__(self, category): self.category = category

def _v0_validate(v, is_key=False):
    if v is None or isinstance(v, bool): return
    if isinstance(v, int):
        if v < -SAFE_MAX or v > SAFE_MAX: raise _V0Reject("INTEGER_OUT_OF_RANGE")
        return
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v): raise _V0Reject("NON_FINITE_NUMBER")
        if struct.unpack(">Q", struct.pack(">d", v))[0] == NEG_ZERO_BITS: raise _V0Reject("NEGATIVE_ZERO")
        if v == int(v) and (v < -SAFE_MAX or v > SAFE_MAX): raise _V0Reject("INTEGER_OUT_OF_RANGE")
        return
    if isinstance(v, str):
        for ch in v:
            if 0xD800 <= ord(ch) <= 0xDFFF: raise _V0Reject("NON_SCALAR_KEY" if is_key else "NON_SCALAR_STRING")
        return
    if isinstance(v, list):
        for it in v: _v0_validate(it)
        return
    if isinstance(v, dict):
        for k, val in v.items():
            if not isinstance(k, str): raise _V0Reject("NON_STRING_KEY")
            _v0_validate(k, is_key=True); _v0_validate(val)
        return
    raise _V0Reject("UNSUPPORTED_TYPE")

def lf_v0_counterfactual(obj, jcs_sha):
    """.v0 for an admitted value == JCS bytes + one LF; rejection is a first-class outcome."""
    try:
        _v0_validate(obj)
    except _V0Reject as r:
        return {"result": "REJECTED", "rejection_category": r.category}
    b = jcs(obj) + b"\n"
    return {"result": "ENCODED", "bytes_hex": b.hex(), "byte_length": len(b),
            "sha256": sha(b), "relation_to_jcs": ("DISTINCT" if sha(b) != jcs_sha else "EQUAL")}

def main():
    fixture = json.loads(sys.stdin.read())
    results = {}
    for v in fixture.get("vectors", []):
        obj = v["inputs"]["object"]
        jsonschema.validate(obj, SCHEMA)                 # schema-valid or the adapter errors -> unverifiable
        jb = jcs(obj); js = sha(jb)
        results[v["name"]] = {
            "conforming_bytes_hex": jb.hex(),
            "conforming_jcs_sha256": js,
            "lf_v0_counterfactual_result": lf_v0_counterfactual(obj, js),
        }
    print(json.dumps({"results": results}))

if __name__ == "__main__":
    main()
