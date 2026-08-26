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

## The wrong-serializer counterfactual leg — DISCHARGED against encode-json-utf8-lf.v0

The LF byte-contract has landed (`encode-json-utf8-lf.v0`, recompute-kit `conformance/encode-json-utf8-lf-v0`),
so the previously-`PENDING` LF leg is now recomputed against it and pinned once in the vectors file to
`contract_id = encode-json-utf8-lf.v0`, `spec_sha256 = 22207f8c…`, `vectors_sha256 = 8d53ab1d…`.

Because `.v0` has a real input domain, the counterfactual is **discriminated, not a boolean** — the field is
`lf_v0_counterfactual_result`, one of:

- **ENCODED** → exact `bytes_hex`, `byte_length`, `sha256`, and `relation_to_jcs` (here `DISTINCT`);
- **REJECTED** → the exact `.v0` rejection category.

Across the four vectors it discharges as **3 ENCODED (`DISTINCT`) + 1 REJECTED**. `jcs_number_edges` carries a
JCS-admitted negative zero and is `REJECTED` as `NEGATIVE_ZERO`: the wrong serializer is out-of-domain entirely,
which is why a boolean "different digest" was too weak a vocabulary — the strongest wrong-serializer evidence in
the set, and the concrete reason `erc-8309.envelope` stays JCS-bound rather than `.v0`.

This is **separate** from `lf_equality_leg` — a hypothetical dedicated object whose stored digest *equals* its own
`.v0` serialization. The `NEGATIVE_ZERO` rejection does **not** close that; the companion (invinoveritas
`erc-8309-vantage` §5) does not mandate such a vector at this head, so it is recorded `SEPARATE_NOT_REQUIRED`. If
the companion ever requires it, add and recompute it as its own vector.

Envelope stays JCS-bound; all four JCS conforming digests are byte-identical to the pre-refresh golden set.

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
