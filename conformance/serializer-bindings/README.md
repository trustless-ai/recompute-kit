# Serializer binding registry

A small, **owner-neutral** registry of immutable records, each binding one named artifact
schema to one **versioned** serializer contract, prospective from an explicit commit. It names
no company and privileges no party — any producer, any binding subject uses the same record
shape (`binding-record.schema.json`).

This directory ships the **shape and its check**, not yet a record. There is no `records/`
directory: a real binding record lands later, and **its authority begins only when it actually
lands** — the schema deliberately does not encode "this PR activates a binding". The registry is
the frozen shape a future record must take.

## What a record is, and is not

The **serializer contract remains the authority.** A binding record is *evidence* that a
specific forward producer actually implements that contract, effective from an exact commit. It
does two things and nothing more:

- names the **`binding_subject`** (e.g. `tsei.frozen-artifact`) and the **`serializer_contract`**
  — its versioned `id` (`encode-json-utf8-lf.v0`) plus its `spec` and `vectors`, each resolved to
  an immutable pre-image;
- fixes the **`effective_commit`** — the producer-adoption boundary, an explicit full SHA, not
  derived from PR or landing time. Artifacts produced at or after it are bound; everything before
  remains historically unversioned.

It carries **`producer_conformance`**: the genuinely-conformant `implementation` adopted at the
boundary, plus a structured `qualification` (it passes the contract's pinned vectors). A producer
that merely *reproduces historical bytes* is not qualified by that alone — byte reproduction is
**migration** evidence that the boundary is backward-identical, not **conformance** evidence for
the implementation.

## Every reference resolves to a pre-image (no bare digests)

A digest does not name what it is the digest *of*. So every reference in a record is a
`source_ref` — **`{repository, revision, path, sha256}`** — where `repository + revision + path`
locate the exact bytes and `sha256` pins them. This applies to `serializer_contract.spec`,
`serializer_contract.vectors`, `producer_conformance.implementation`, and the vectors named in
`qualification`. `effective_commit` names a *commit*, not a file, so it carries `{repository,
commit}` only.

`qualification` is structured, not prose:

```
"qualification": {
  "method": "passes-pinned-serializer-vectors",
  "vectors": { repository, revision, path, sha256 },
  "vector_count": <int ≥ 1>
}
```

The one semantic JSON Schema cannot state, enforced by the validator: **`qualification.vectors`
MUST be the same immutable pre-image as `serializer_contract.vectors`.** "Passes the pinned
vectors" is only evidence if they are *this* contract's vectors.

## Non-retroactivity (machine-checkable, not prose)

Every record declares `non_retroactivity` with three `const: true` facts:

- `prospective_only` — governs only artifacts at or after `effective_commit`;
- `byte_reproduction_is_not_binding` — a historical artifact re-encoding byte-identically does
  **not** become a contract artifact;
- `historical_binding_requires_separate_record` — deliberately binding a historical identity, if
  ever chosen, needs its own separate immutable legacy-resolution record.

## Files

- `binding-record.schema.json` — the frozen record shape (draft-07). No `$id`: where this registry
  ultimately lives is an open question, so it is placed under no owner; a stable owner-neutral URI
  is added when the commons home is decided, not before.
- `binding-record.vectors.json` — **shape** vectors: one valid forward binding + eleven negative
  controls, each pinned to the exact rejection token, so every rule is proven able to fail. These
  test the shape, not a real binding (coordinates are synthetic but well-formed).
- `validate_binding_record.py` — the checker. Pure stdlib; it reads the schema and enforces it
  directly (a subset of draft-07), then applies the cross-field semantic above. Exit `0` all
  reproduced, `1` a determinate mismatch, `2` the checker itself could not run.
- `suite.json` — wires this into `tools/run_conformance.py` so the registry is *covered*, not
  merely present.

## Adding a record (when one lands)

1. Write `records/<binding_subject>.json`.
2. It MUST validate against `binding-record.schema.json`.
3. `serializer_contract.spec` / `serializer_contract.vectors` MUST resolve to the referenced
   contract's real pre-images, and `qualification.vectors` MUST equal `serializer_contract.vectors`.
4. `producer_conformance.implementation` MUST name a conformant producer, not a byte-coincidental
   predecessor.
