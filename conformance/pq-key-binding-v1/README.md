# pq_key_binding.v1 — temporal authority

Vectors for the proposed v1 temporal model: **`governs_from` is derived from
anchors, never stored.**

Spec: `trustless-ai/pq-agent-binding` → `spec/v1-temporal-authority.md` (PR #1).

```bash
python3 temporal_resolve.py          # exit 0 if every check reproduces
```

## What v0 got wrong

v0 said an epoch-0 binding governs `[T0, Trot)` and never defined `T0`.
Implementations supplied it from local state, which made the boundary
**verdict-bearing without being commitment-bearing**: it is not in the JCS
statement, so it never reaches the content address, the leaf, or any anchored
root. The same committed statement, same leaf and same anchored root could
therefore yield a different verdict — and no root recomputation could detect it.

## The rules

| | |
|---|---|
| **R1** | `key_epoch 0` → `governs_from = 0` |
| **R2** | `key_epoch n>0` → `anchored_at` of the **earliest** anchored batch containing the binding's `cc` |
| **R3** | `key_epoch n>0` with no containing anchor → no authority, never in force |
| **R4** | greatest eligible `governs_from` wins, revocation ends authority |
| **R5** | `submitted_at` MUST NOT affect any verdict |

## Data

Real values from a live deployment (agent 8, registry `0x8b5af3a5…c3`), so the
leaves and anchor timestamps can be cross-checked against the published anchors
and on-chain calldata rather than trusted. Anchor epoch 3 is synthetic and
labelled as such — it exists only to pin R2's *earliest*.

## Two checks that are the point

**`submitted-at-is-not-verdict-bearing`** and
**`baseline-submitted-at-is-not-verdict-bearing`** mutate a stored field and
require the verdict not to move. They test the *shape* of the dependency rather
than its value, because a suite that only checks implementations agree can never
find a field they all read the same wrong way — which is exactly how v0's defect
survived two independent verifications.

`temporal_resolve.py` also scans its own resolution functions and fails if
`submitted_at` appears in them. A comment promising not to read a field is not a
control.

## Two holes this suite found in itself

Worth recording, because both are the failure mode the suite exists to catch:

1. The R5 source scan first scanned the whole file and flagged **its own detector
   lines** — a check reporting a problem it had created.
2. A negative control (deliberately reintroducing the defect) passed every
   value-based case, because `e0.submitted_at` is `0`, which *coincides* with
   R1's correct answer. Only the source scan caught it.
   `baseline-submitted-at-is-not-verdict-bearing` was added to close that: it
   moves `e0.submitted_at` to a value that would change the verdict, so the
   defect now fails by value too.

Two fields agreeing on one dataset is not the same as one of them being unread.
