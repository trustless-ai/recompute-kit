# `encode-json-utf8-lf.v0` conformance

This directory publishes the prospective, language-neutral byte contract and
golden vectors for `encode-json-utf8-lf.v0`. It does not bind any producer to
the contract. In particular, this surface does not migrate
`ccip.attestation.unsigned.v1`, `tsei.frozen-artifact`, or
`recompute-kit.artifact`.

The contract is intentionally not JCS. It imports only the binary64 number
serialization algorithm cited by RFC 8785 section 3.2.2.3. Its input-domain
validation, serializer identity, terminal-LF framing, and prospective boundary
are specified independently.

## Run

From this directory:

```text
python encoder.py
bun encoder.ts
python gate.py
python gate.py --negative-controls
```

The normal gate verifies the pins in `suite.json`, executes every vector with
both adapters, checks each adapter against the frozen result, checks the two
adapters against each other, and proves all six negative controls go red. The
explicit `--negative-controls` mode runs only those controls.

The vector JSON uses tagged fixture transport. Tags such as `f64_bits` and
`integer` preserve the abstract input exactly; they are not part of the
serializer's output format.

## Authority and identity

The authority for this suite is the hash-pinned specification plus the
hash-pinned vector file—not either adapter. There is no floating alias:
`encode-json-utf8-lf` does not mean “latest” and does not resolve to v0 without
a separate, explicit, immutable versioned binding record.

Candidate-byte acceptance is outside this surface. Raw-byte mutations such as
BOM, CRLF, malformed UTF-8, duplicate JSON members, or trailing bytes are not
encoder inputs and are not modeled as encoder-domain vectors here.
