# convention-hash.v0 — governing-convention pinning for versioned computations

A computation rule can evolve (rounding, representation, formula). When it does, any **persisted signed
value** produced under the old rule must stay **recomputable** — otherwise a verifier applying the *new*
rule fails to reproduce it and reports a false mismatch. This profile pins the fix: **pin-at-issuance,
resolve-at-verification.**

## Rule

- A convention's identity is **content-addressed over its exact spec**:

  ```
  governing_convention_hash = "0x" + sha256( JCS(convention_spec) )
  ```

  where `convention_spec` pins the **formula, representation, and rounding mode** — because number
  formatting and rounding are exactly where two honest implementations diverge without disagreeing on the
  plain-English description. Two ways of computing the "same" quantity are **two hashes**.

- At **issuance**, the producer records the `governing_convention_hash` of the convention that produced
  the value.

- At **verification**, the verifier **resolves that hash** to the exact convention and recomputes the
  value **under that convention — never the current default.** Then, tri-state, fail-closed:

  ```
  verified      iff  recompute-under-pinned-convention(inputs) == value
  rejected      iff  it does not
  unverifiable  iff  the governing_convention_hash is unknown   (fail closed — never a silent pass)
  ```

## Registered conventions (ERC-8275 win-rate)

Two genuinely exist as of the basis-points cutover (agent-sdk#5; `winRateBps` live on babyblueviper
`/ledger`):

| convention | rule | `governing_convention_hash` |
| --- | --- | --- |
| `win_rate.float-4dp.v0` | `round(wins/(wins+losses), 4)` — float, 4 dp, round-half-to-even | `0xf08010c4…0227` |
| `win_rate.bps.v0` | `(wins*20000 + total) // (2*total)` — exact integer, **round-half-up** | `0x0501b75d…8daf` |

The full pinned specs (with rounding mode) are carried in `convention-hash-v0.vectors.json`; the hashes
above are `sha256(JCS(spec))` over those exact objects.

**Converged against the shipped code, not inferred.** The `bps` rule is locked to `trustless-ai/agent-sdk#5`
(`@87b08f3`, reputation/erc8275 — Python/Rust/TS identical: `(wins*20000 + total)//(2*total)`, half-away-
from-zero, *"Never a float round()"*), and this suite **reproduces its golden vectors** —
`0/15→0`, `16/0→10000`, `1/2→3333`, `16/15→5161`. An earlier *inferred* rule (`round(...)`, round-half-to-
**even**) produced a different hash and a different value at ties — e.g. `1 win / 31 losses` = exactly
312.5 bps → **313** under the shipped round-half-up vs **312** under round-half-even. That 1-bps split is
exactly what the `governing_convention_hash` makes explicit instead of silent.

## Why it matters (the disambiguation)

For `wins=19, losses=1` the two conventions produce **different persisted values** — `0.95` vs `9500`.
A value of `0.95` verifies **only** under `float-4dp`; a verifier that assumed the new `bps` convention
would recompute `9500`, reject `0.95`, and wrongly flag a good value. The `governing_convention_hash` is
what keeps the old value verifiable after the cutover.

## Vectors

`convention-hash-v0.vectors.json` pins: a match under each convention; **an old float value graded under
the bps convention → `rejected`** (the exact failure the pointer prevents); a genuinely wrong value →
`rejected`; and an **unknown convention hash → `unverifiable`** (fail-closed). An implementation is
conformant iff it reproduces every verdict.

## Out of scope (v0)

- The reputation aggregate (which wins/losses feed the win-rate) — that's ERC-8275's own recompute.
- Non-win-rate conventions — the mechanism is general; only the two win-rate conventions are registered
  here.
