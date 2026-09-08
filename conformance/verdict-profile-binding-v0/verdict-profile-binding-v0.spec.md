# verdict-profile-binding.v0

The **resolution end** of the profile-commitment loop. [`profile-amendment-v0`](../profile-amendment-v0/)
decides which verification profile is *effective* for a task (the amendment end); this decides whether the
resolver's verdict actually **commits, in its signed preimage, to that effective profile** — so
"I resolved under this profile" is attested and recomputable, not a side-channel reference.

## Why

Pinning the profile at task creation and authorizing amendments only closes half of
`task.profile_commitment == verdict.profile_commitment` (@Pavlentyy82, WG 2026-09-08). The other half is at
resolution: a resolver could resolve under the correct effective profile and still emit a verdict that does
not commit to it, leaving the same side-channel gap @babyblueviper1 flagged on recompute-kit #40, moved to
the resolution end. This suite closes it with the companion-envelope shape applied to the profile.

## Construction

```
verdict_core    = { ...verdict fields..., effective_profile_commitment }   # the profile is IN the core
verdict_core_cc = sha256(JCS(verdict_core))                                # what the resolver signs
resolver_sig    = { signed_digest, pubkey }                               # signed_digest MUST == verdict_core_cc
```

`JCS` / `sha256` identical to companion-envelope-v0 and profile-amendment-v0.

## Rule

A verdict is **bound** to its profile iff, together:

1. **Profile in preimage** — `verdict_core.effective_profile_commitment` is present AND equals the task's
   authorized `effective_profile_commitment` (the value `profile-amendment-v0` produced). It resolved under
   the profile that was actually in force.
2. **Signed here** — the resolver signed *this* core: `signed_digest` present AND == `verdict_core_cc`.

Otherwise `resolution_status` is `"unresolved"` and `bound_profile_commitment` is `null` — a verdict that
omits the profile, names a different one, or is signed over some other core certifies nothing. Fail closed,
`unresolved` never a silent bind.

## Composition

```
profile_transition(task).effective_profile_commitment == verdict.core.effective_profile_commitment
```

`profile-amendment-v0` establishes the left side (which profile is effective, and that the change to it was
co-signed); this suite establishes the right side (the resolver signed a verdict carrying exactly that). The
suites meet at one value — the vectors here use the same `sha256(JCS(profileB))` that `profile-amendment-v0`'s
`permitted` case produces — so together they are Pavlo's invariant with both ends cryptographic.

## Scope

Checks the **binding** (`signed_digest == verdict_core_cc`), not signature cryptography. ECDSA / ML-DSA
validity of the resolver signature rides the separate signature lane.

## Vectors

Six, in `verdict-profile-binding-v0.vectors.json` — two bound, four refused, one negative per predicate:

- `bound` — profile in preimage, resolver signed this core → bound
- `bound-distinct-verdict` — different verdict payload, still carries the profile and is signed over its own
  core → still bound (verdict fields may vary; shape not value)
- `profile-omitted` — core does not carry `effective_profile_commitment` → unresolved (the side-channel gap)
- `wrong-profile` — core commits to a profile != the task's authorized one → unresolved
- `signature-over-wrong-core` — right profile, but resolver signed some other core → unresolved
- `resolver-absent` — no resolver signature → unresolved

Reproduced byte-for-byte by both `verdict_binding_gate.py` and `verdict-profile-binding-v0.reference.mjs`
(bun/node, independent `jcs`); each reds on a refuted vector.
