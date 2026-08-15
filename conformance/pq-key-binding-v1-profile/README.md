# pq_key_binding.v1 — profile over `captured-admission.v0`

**This directory adds no checker code.** It reuses `admission_check.py` from the
frozen core, unmodified:

```bash
python3 ../captured-admission-v0/admission_check.py vectors.json   →  15/15
```

Core checker `sha256 7a2369ae889419318629a33e16a9f683939cfcf787478d4e38284ef9ec23f471`
— the freeze at `a724afc`. Unchanged by this profile, verifiable on the bytes.

## What was under test

Six rounds of design produced a temporal model for PQ key bindings. The question
these vectors answer is whether that model is a **new mechanism** or a **profile
over machinery that already existed**.

It is a profile. The core proves the state machine; the profile's only real
contribution is **deriving the activation boundary from anchors** instead of reading
it from implementation state. That derivation was the entire defect:

```
baseline   activated_at = 0        — the key governs from creation; anchoring gives a
                                     binding a provable time, not a birthday
successor  activated_at = anchor timestamp of the EARLIEST anchored batch
                                     containing the binding's leaf
never      a producer-held timestamp
```

## Cases

| case | mode | verdict |
|---|---|---|
| `PQ_baseline_governs_from_zero` | authority | `attributed` |
| `PQ_successor_in_pre_anchor_window_out_of_authority` | authority | `out_of_authority` |
| `PQ_successor_after_anchor_attributed` | authority | `attributed` |
| `PQ_unanchored_successor_not_yet_active` | authority | `epoch_not_yet_active` |
| `PQ_rotation_is_not_retroactive` | authority | `attributed` |
| `PQ_rotation_without_bound_successor_invalid` | authority | `invalid_transition` |
| `PQ_ack_equivocation_same_seq_two_objects` | enumerate | `conflicting_index:1` |
| `PQ_skipped_epoch_is_a_sequence_gap` | enumerate | `gap:2` |
| `PQ_admission_head_must_match_anchor` | enumerate | `commitment_mismatch` |

Values are the real ones from a live deployment (agent 8 of registry
`0x8b5af3a5…c3`): epoch-0 leaf `856aecef…`, epoch-1 leaf `81aec993…`, anchor 1 at
`1785436450`, anchor 2 at `1786549450`, rotation submitted `1786548015` — **1435
seconds before its anchor.** That gap is the live divergence, and
`PQ_successor_in_pre_anchor_window_out_of_authority` is it.

## What building these found

**`requires_supersede_successor` already exists as a profile flag.** We designed an
owner-signed `predecessor_binding_cc → successor_binding_cc` authorization over
several rounds; the core had the property waiting as a switch nobody had turned on.
`PQ_rotation_without_bound_successor_invalid` turns it on.

**The first attempt crashed.** The transition shape was wrong — `successor_epoch_id`
instead of `successor_epoch`, `supersede` instead of `superseded`. That crash is the
reason this exercise was worth doing: a semantic mapping in a table would have read
as agreement, and the checker refused it. Nothing here was proven until it ran.

## False-positive cases (`FP_*`)

`conflicting_index` and `out_of_authority` are the only verdicts here that make a
**positive accusation about a named party**. Detecting equivocation is one property;
never *crying* equivocation when there is none is the other, and only the first was
tested.

| case | must be | must NOT be |
|---|---|---|
| `FP_retransmitted_ack_is_duplicate_not_equivocation` | `duplicate:1` | `conflicting_index` — a client retry is not a producer contradiction |
| `FP_out_of_order_delivery_is_not_equivocation` | `out_of_order` | `conflicting_index` — disorder is not contradiction |
| `FP_gap_is_not_a_conflict` | `gap:1` | `conflicting_index` — absence is not contradiction |
| `FP_claim_exactly_at_activation_is_attributed` | `attributed` | `out_of_authority` — the off-by-one that strips a real artifact |
| `FP_later_rotation_does_not_strip_earlier_authority` | `attributed` | `out_of_authority` — the companion bug's exact shape |
| `FP_another_agents_rotation_does_not_affect_this_one` | `attributed` | `out_of_authority` — epoch scoping, which matters in a fleet |

Expected verdicts were written from design intent **before** running. All six matched
on the first execution.

### They were then checked for discrimination

A case that passes is not necessarily a case that tests anything. Each `FP_` case was
re-run with the verdict an **over-accusing** implementation would return, and all six
produced `BAD` with exit 1 — so each genuinely rejects the false positive rather than
passing vacuously.

The first discrimination check reported the opposite. It grepped stdout for `"FAIL"`;
the checker prints `"BAD"`. A detector looking for the wrong string reported six
non-discriminating vectors that discriminate perfectly — the same defect this profile
exists to remove, in the tool built to confirm its absence. Redone against the `BAD`
marker and the exit code.

## What the profile still owns

The core takes an activation boundary as input and never says where it comes from.
Outside these vectors, the profile owns:

1. deriving `governs_from` from the earliest containing anchor
2. the owner-signed, domain-separated transition authorization
3. `seed_epoch` — the master-seed axis, PQ-specific: all agent keys derive from one
   seed, so only a seed rotation remediates a seed compromise
4. `legacy_bindings_root` — freezing bindings that predate any sequence, since
   backfilling acceptance records for them would manufacture evidence

Spec: `trustless-ai/pq-agent-binding` → `spec/v1-temporal-authority.md` (PR #1).
