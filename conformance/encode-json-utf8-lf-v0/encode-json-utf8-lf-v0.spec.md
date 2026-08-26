# `encode-json-utf8-lf.v0`

## 1. Identity and scope

The normative contract identifier is exactly:

```text
encode-json-utf8-lf.v0
```

The version suffix is part of the identity. This identifier resolves to one
immutable specification digest and one immutable conformance-vector digest.
Any future normative change requires a new identifier. The unversioned string
`encode-json-utf8-lf` MUST NOT mean “latest”, MUST NOT float to a future
version, and MUST NOT be treated as v0 without an explicit versioned binding
record.

This publication defines an encoder contract only. It does not migrate any
live serializer binding and does not define a raw-byte parser or byte-acceptor.

## 2. Abstract input values

The encoder consumes an abstract typed value. The following values are
permitted recursively:

- null;
- boolean;
- a number admitted by section 3;
- a Unicode scalar-value string;
- an array of permitted values;
- an object with unique Unicode scalar-value string keys and permitted values.

Array order is preserved. Host-language types are non-normative. In
particular, a Python `int(1)`, Python `float(1.0)`, and ECMAScript `Number(1)`
all map to the same abstract binary64 value and serialize as `1`.

The tagged representation in the vector file is fixture transport only and is
not part of the serialized format.

## 3. Numbers

An admitted number is ultimately an IEEE-754 binary64 value, including its
sign bit. A host adapter MUST NOT silently round a higher-precision value into
this domain.

Validation occurs before rendering, in this order:

1. An exact mathematical integer MUST lie in
   `[-9007199254740991, 9007199254740991]`; otherwise the encoder rejects it as
   `INTEGER_OUT_OF_RANGE`. Every integer inside that interval is exactly
   representable as binary64.
2. A non-integral higher-precision host value may be admitted only when exact
   representability as finite binary64 is proven; otherwise the encoder rejects
   it as `NUMBER_NOT_EXACTLY_BINARY64`.
3. A binary64 NaN or positive or negative Infinity is rejected as
   `NON_FINITE_NUMBER`.
4. The negative-zero binary64 bit pattern is rejected as `NEGATIVE_ZERO`.
5. If the resulting binary64 value is mathematically integral, it MUST lie in
   the safe-integer interval above; otherwise it is rejected as
   `INTEGER_OUT_OF_RANGE`.

Only an admitted value is rendered. Rendering MUST use the ECMAScript number
serialization algorithm identified by RFC 8785 section 3.2.2.3, including its
reference to ECMAScript's enhanced shortest representation. This imports only
that scalar number-rendering algorithm. This serializer is not JCS, and JCS
object serialization is not an authority for this contract.

Consequently, binary64 `1.0` renders as `1`, binary64 `1e-7` renders as
`1e-7`, while binary64 `1e20`, binary64 `1e21`, and negative zero are rejected
before rendering.

## 4. Object keys

Every object is sorted recursively. Keys are compared in their raw, unescaped
form as sequences of unsigned UTF-16 code units, lexicographically and without
locale influence. If one sequence is a prefix of another, the shorter sequence
sorts first.

Supplementary scalar values participate through their UTF-16 surrogate-pair
code units for comparison only. Lone surrogates are not scalar values and are
invalid input. Therefore U+1F600 sorts before U+FFFF. Python implementations
MUST implement this comparison explicitly and MUST NOT use native code-point
sorting.

## 5. Strings and escaping

Keys and string values MUST contain Unicode scalar values only. The encoder
performs no Unicode normalization, case folding, or replacement. Composed and
decomposed sequences remain byte-distinct. A lone surrogate in a value is
rejected as `NON_SCALAR_STRING`; a lone surrogate in a key is rejected as
`NON_SCALAR_KEY`.

String escaping is exact:

- `"` is emitted for U+0022;
- `\\` is emitted for U+005C;
- `\b`, `\f`, `\n`, `\r`, and `\t` are emitted for U+0008, U+000C, U+000A,
  U+000D, and U+0009;
- every remaining U+0000 through U+001F value is emitted as lowercase
  `\u00xx`;
- U+002F is not escaped;
- every other scalar value is emitted literally as UTF-8, including U+2028
  and U+2029.

## 6. Framing

The encoder emits a compact JSON body with no insignificant whitespace,
encoded as UTF-8 without a BOM, followed by exactly one byte `0a`. It emits no
CR framing and no byte after the terminal LF.

These are output invariants. BOM-prefixed bytes, CRLF bytes, missing or extra
LF bytes, trailing bytes, malformed UTF-8, and duplicate-key JSON token streams
belong to a separate candidate-byte or parser conformance surface; they are not
abstract encoder inputs.

## 7. Fixture transport

The vector transport encodes abstract values with explicit tags:

- `{"type":"null"}`;
- `{"type":"boolean","value":true|false}`;
- `{"type":"string","value":"..."}`;
- `{"type":"integer","decimal":"..."}` for an exact mathematical integer;
- `{"type":"f64_bits","hex":"................"}` for an exact 64-bit
  binary64 payload in big-endian hexadecimal;
- `{"type":"array","items":[...]}`;
- `{"type":"object","entries":[{"key":"...","value":...},...]}`.

Ordinary JSON numeric tokens are not used to carry normative numeric inputs.

RFC 8785 Appendix B values are first classified through section 3. Only
in-domain rows are rendering successes. Negative zero, nonfinite rows, and
mathematically integral rows outside the safe interval are contract
rejections, even where Appendix B displays an ECMAScript rendering.

## 8. Historical boundary

This contract is prospective. Historical TSEI artifacts are never rewritten,
reserialized, or rehashed to conform to v0. Existing unversioned
`encode-json-utf8-lf` records do not automatically resolve to v0.

Any legacy resolution requires a separate immutable record scoped to an exact
historical binding identity, containing an exact effective boundary, the exact
`encode-json-utf8-lf.v0` specification digest, and the exact vector digest. No
global legacy alias is created.
