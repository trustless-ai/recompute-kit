#!/usr/bin/env python3
"""erc-8309.envelope golden-set adapter — recompute-and-compare, recompute-kit contract.

Reads the vectors fixture on STDIN (the grader pipes it in), reads the erc-8309.envelope schema
from the suite dir, and for each vector re-derives the answer from inputs.object:
  - validate the object against the schema;
  - serialize it under the bound serializer RFC 8785 JCS (no trailing byte) -> conforming bytes;
  - serialize it under encodeJsonUtf8Lf and confirm that digest DIFFERS from the JCS digest
    (wrong-serializer rejection, earned by recompute).
Emits {"results": {name: {conforming_bytes_hex, conforming_jcs_sha256, distinct_from_lf}}}, which
the grader compares to each vector's `expected`. Nothing here trusts the stored expected values;
they are re-derived and the grader does the comparison.

Deps: rfc8785 (RFC 8785 JCS), jsonschema.
The LF-equality vector is pending the LF byte-contract binding; recorded PENDING in the fixture.
"""
import json, hashlib, sys, os
import rfc8785, jsonschema

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "erc-8309.envelope.schema.json")))

def jcs(o): return rfc8785.dumps(o)
def lf(o):  return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
def sha(b): return hashlib.sha256(b).hexdigest()

def main():
    fixture = json.loads(sys.stdin.read())
    results = {}
    for v in fixture.get("vectors", []):
        obj = v["inputs"]["object"]
        jsonschema.validate(obj, SCHEMA)                 # schema-valid or the adapter errors -> unverifiable
        jb = jcs(obj)
        results[v["name"]] = {
            "conforming_bytes_hex": jb.hex(),
            "conforming_jcs_sha256": sha(jb),
            "distinct_from_lf": sha(jb) != sha(lf(obj)),
        }
    print(json.dumps({"results": results}))

if __name__ == "__main__":
    main()
