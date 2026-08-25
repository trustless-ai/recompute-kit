# erc-8309-envelope-v0 — resolution-envelope golden set (§5 `erc-8309.envelope`)

Hash-pinned conformance vectors for the ERC-8309 vantage-authority companion's **resolution envelope**
(§5, E1–E6). The binding's canonical serializer is **RFC 8785 JCS, no trailing byte**, named in the
schema's own `x-canonical-serializer` — a schema that does not name its serializer forces every consumer
to infer one, the exact defect the per-schema rule was ratified to remove.

## What it pins

`erc-8309-envelope-v0.vectors.json` — the golden set, **derived from the byte definition, not hand-written**:
each vector is a schema-valid envelope object plus the exact JCS bytes it serializes to (`bytes_hex` the
normative carrier) and its digest. Edge cases are chosen so the pin survives them — non-ASCII content, JCS
number canonicalisation (`0.5`, `-0.0`), and unsorted input keys — because conforming envelope bytes are
determined by RFC 8785 JCS alone, including its number and string rules.

The gate (`erc-8309-envelope-grade.py`) **recomputes and compares** — it re-derives each object's JCS bytes
and requires them byte-identical to the stored ones, and requires the same object's `encodeJsonUtf8Lf` digest
to *differ* from the JCS digest (wrong-serializer rejection earned by recompute, since `encodeJsonUtf8Lf`
emits one trailing `0x0a` and is a separately-bound serializer — the same object digests to unrelated hashes
under the two). A checker that can only pass proves nothing when the encoder is wrong.

## Partial discharge — the LF-equality leg is PENDING, not missing

One vector is deliberately absent: the failure-comparison entry whose digest *equals* the same object's
`encodeJsonUtf8Lf` serialization. That equality needs the **LF byte-contract binding**, which is not yet
specified in any normative serializer-contract artifact (Pavlo's leg). The vectors file records this as
`lf_equality_leg: PENDING` with a machine-readable closing condition — absence stated, never blurred into done.
When the LF byte-contract lands, add that vector and recompute.

## Provenance

Schema pinned by `spec.sha256` and `upstream` (the erc-8309.envelope schema at invinoveritas @ f88d5263).
This suite carries its own definition-derived leg — the vectors are re-derivable by anyone from the schema
and the JCS rules, not agreed by matching an implementation.

## Run

```bash
bin/conformance-suite --suite conformance/erc-8309-envelope-v0     # pins vectors+spec by sha, runs the gate
# or directly:
cat conformance/erc-8309-envelope-v0/erc-8309-envelope-v0.vectors.json | \
  python3 conformance/erc-8309-envelope-v0/erc-8309-envelope-grade.py   # {results:{...}}
```

Deps: `rfc8785` (RFC 8785 JCS), `jsonschema`.
