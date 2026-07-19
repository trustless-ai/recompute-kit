# recompute-kit conventions

House rules every vector and every language SDK inherits by reference, so nobody
rediscovers them per-formula.

## Numeric convention

Any recomputed value two implementations must reproduce **bit-identically** follows one rule:

1. **Exact internally.** Compute in exact integers or rationals — never binary float — through
   the whole recompute. (Jaccard sums, cap arithmetic, gated ratios are all exact.)

2. **Round only at the boundary, with a named mode.** Any rounding to a display/tolerance
   precision is a single, named mode — **ROUND_HALF_UP over exact `Decimal`** — applied once at
   the output. **Never a bare float `round()`.** Bare float rounding diverges across languages:
   Python `round()` is banker's (half-to-even), Rust `f64::round()` is half-away-from-zero, JS
   `.toFixed()` is neither reliably — they disagree on any ratio landing on a decimal tie
   (e.g. `wins=1, losses=31` → `1/32 = 0.03125` → `0.0312` vs `0.0313`).

3. **Tolerance is spec'd, not implied.** A vector states its rounding mode + precision;
   conformance is exact reproduction of that value, not "close enough."

### Why this is a rule and not a comment

Surfaced **three times independently** before being written down — the Rust core's `f64::round`,
the kit's `/ledger` winRate handler, and the ERC-8275 attester-independence tolerance. That's the
tell that it's doctrine, not preference. A formula that follows it (e.g. attester-independence:
`N² / Σᵢⱼ Jaccard`) keeps exact rationals internally and rounds only at the display boundary,
half-up — so its tolerance just cites this file.
