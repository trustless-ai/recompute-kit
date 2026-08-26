# Serializer binding registry

A small, **owner-neutral** registry of immutable records, each binding one named artifact
schema to one **versioned** serializer contract, prospective from an explicit commit.

It lives next to the serializer contract it references (`conformance/encode-json-utf8-lf-v0/`)
because it is the same kind of object: a pinned, digest-anchored, recomputable claim. It names
no company and privileges no party — any producer, any binding subject uses the same record
shape (`binding-record.schema.json`).

## What a record is, and is not

The **serializer contract remains the authority.** A binding record is *evidence* that a
specific forward producer actually implements that contract, effective from an exact commit. It
does two things and nothing more:

- names the **binding subject** (e.g. `tsei.frozen-artifact`), the **serializer contract id**
  (`encode-json-utf8-lf.v0`) and its pinned `spec_sha256` / `vectors_sha256`;
- fixes the **`effective_commit`** — the producer-adoption boundary, an explicit full SHA, not
  derived from PR or landing time. Artifacts produced at or after it are bound; everything before
  remains historically unversioned.

It carries **`producer_conformance`**: the genuinely-conformant implementation adopted at the
boundary, plus the evidence qualifying it (it passes the contract's pinned vectors). A producer
that merely *reproduces historical bytes* is not qualified by that alone — byte reproduction is
**migration** evidence that the boundary is backward-identical, not **conformance** evidence for
the implementation.

## Non-retroactivity (machine-checkable, not prose)

Every record declares `non_retroactivity` with three `const: true` facts:

- `prospective_only` — governs only artifacts at or after `effective_commit`;
- `byte_reproduction_is_not_binding` — a historical artifact re-encoding byte-identically does
  **not** become a contract artifact;
- `historical_binding_requires_separate_record` — deliberately binding a historical identity, if
  ever chosen, needs its own separate immutable legacy-resolution record.

## Adding a record

1. Write `records/<binding_subject>.json`.
2. It MUST validate against `binding-record.schema.json`.
3. `spec_sha256` / `vectors_sha256` MUST equal the pinned digests of the referenced contract.
4. `producer_conformance.implementation` MUST name a conformant producer, not a byte-coincidental
   predecessor; `qualification` MUST cite its conformance evidence.

## Home

`$id` is intentionally a placeholder. Where this registry ultimately lives is an open question —
the point is that it isn't owned by any one producer, so it is not being placed under one.
