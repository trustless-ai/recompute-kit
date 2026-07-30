# aggregate_budget.v0 — root-keyed conservation, recomputed from the Drawn log

**Profile:** `aggregate_budget.v0` · **Lane:** recomputable · **Layer:** ERC-8312 (bounded agent actions)

The event-log complement to the storage-proof `cap-conservation` recipe. Where cap-conservation
proves `reserved + confirmed ≤ cap` against a storage slot pinned to a `stateRoot` (the
indexer-uncheatable audit half), this profile recomputes the **same conservation** directly from the
**`Drawn` event log**, so the two views reconcile: the meter slot value *is* Σ of the admitted draws.

## The predicate

For a pinned `(rootId, periodIndex)` and its pinned root `cap`:

```
admittedSum = Σ { e.amount : e ∈ log ∧ e.rootId = rootId ∧ e.periodIndex = periodIndex ∧ e.admitted }
conserves   = admittedSum ≤ cap
```

- **The conserved carrier is ONE root-keyed meter.** Conservation is asserted over the *root*, summed
  across every edge-attributed draw for the period.
- **Edge / node is attribution, never the conserved quantity.** `e.edge` is a breakdown label — which
  delegate/leaf a draw is *attributed* to — carried alongside the amount, not summed as its own budget.
- **Admission is the gate.** Only `admitted` draws touch the meter; a rejected attempt never counts.
- **`(rootId, periodIndex)` is a stored key.** The period is a stored index, not a wall-clock window,
  so the predicate is assertable at any observing block with no timestamp replay.

## The counterexample — why per-edge is non-conformant

The `fanout-exceeds-root-cap` vector is the load-bearing one. Three edges draw `900 / 800 / 700`;
each is individually under the `2000` cap, so **a per-edge counter treated as the aggregate passes all
three** — yet the root-keyed sum is `2400 > cap`. A fan-out / re-delegation spins up fresh edges
precisely to spread draws so no single edge exceeds the cap. Root-keyed conservation reports the
non-conservation; a per-edge view is the leak the profile exists to close. `--tamper` in the adapter
computes by exactly that wrong method (max per-edge subtotal as the aggregate); it flips this vector to
a false `conserves: true` and mismatches — so the suite fails, on purpose.

## Two honest bounds (the claim does not overreach)

1. **Metered-only.** The predicate asserts `Σ metered draws ≤ cap` **only over draws routed through the
   meter.** Non-bypassability — that every consuming path emits an admitted `Drawn` — is the
   substrate's obligation, stated by the profile, **not** something this recompute proves.
2. **Period-scoped.** The bound is for the pinned `(rootId, periodIndex)`; draws in another period or
   under another root are a different meter and are excluded (`period-index-isolation`,
   `cross-root-isolation`).

## The predicate-not-number principle

> A conformance vector pins a **predicate and the method of deciding it — not merely the output
> numbers.** A candidate that reproduces the numbers by an unsound method must still fail. Therefore the
> vector set must carry the **counterexample that only the sound method decides correctly** — the
> negative vector sits exactly at the predicate a wrong implementation would skip. Reproducing outputs
> is not implementing the predicate; the counterexample is what forces the method.

Here that is `fanout-exceeds-root-cap`: any implementation that "sums a budget" but keys it per-edge
reproduces every *other* vector and fails only this one. Conformance is reproducing **every** expected
from the same inputs — so the counterexample is what the profile actually tests. This generalizes: for
any conserved-quantity predicate, pin the vector where the sound aggregation and the tempting-but-wrong
aggregation disagree.

## Constructive unreachability (safety-by-construction)

`fanout-exceeds-root-cap` is stronger than a vector that flags a violation after the fact: on a sound
implementation the non-conserving log is **unreachable, not merely rejected**. Verified against the
reference `AggregateBudgetCursor` (an independent third implementation; stdlib recompute + Forge replay,
7/7 at `afab44c`): draws of 900 and 800 admit; the 700 that would make 2400 **reverts
`RootBoundExceeded`** and the meter stays at 1700. So the non-conserving trace is precisely a log a sound
implementation **cannot emit** — the vector's predicate coincides with the contract's *reachability
boundary*.

This sharpens **predicate-not-number**: the counterexample isn't an error to catch downstream, it's a
state the conserved-meter construction forbids at the source. The recompute side (this suite) and the
construction side (the reverting cursor) meet on the same fact from two directions — the log-level
predicate and the on-chain impossibility are one conservation law.

## Adapter contract

`bin/conformance-suite` feeds the vectors JSON on stdin and reads `{ name: { admittedSum, conserves } }`
on stdout (`bun gate.ts --grade`). Conformant iff every `expected` is reproduced. The run is itself
recomputable; the vectors are hash-pinned in `suite.json` (fail-closed on mismatch).
