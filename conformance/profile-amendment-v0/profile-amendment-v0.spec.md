# profile-amendment.v0

Recompute whether a change to a task's **verification profile** is an *authorized amendment* or an
*unauthorized swap*. Sibling to [companion-envelope-v0](../companion-envelope-v0/): companion-envelope
binds a verdict to its companion; this binds a profile *change* to a co-signed transition, so the
resolution semantics both sides bonded into cannot be silently altered after the task is accepted.

## Why

A verification profile declares which claims are mechanically checkable, which evidence is admissible,
and which are jury-resolved. If it can change between task-creation and resolution, a resolver can settle
under rules neither side agreed to. Pinning the profile at task-creation is only half the closure: a
legitimate amendment and an unauthorized substitution are **indistinguishable at the hash level** unless
the change itself is bound and co-signed. Authorization must be *evidenced by the transition artifact*,
never inferred from the fact that the profile hash is now different.

(Origin: trustless-ai WG, 2026-09-08 — @Pavlentyy82's three-case transition contract and @babyblueviper1's
signed-preimage requirement, over the Apex-Fusion agents-marketplace Module-1 dispute design. This is the
two-party generalization of the single-owner [pq-key-binding-v0](../pq-key-binding-v0/) rotation edge; the
resolution shape — the binding in force at the artifact's anchor time governs — is the same.)

## Construction

```
prior_profile_commitment = sha256(JCS(in_force_profile))
new_profile_commitment   = sha256(JCS(proposed_profile))
amendment (preimage)     = { schema: "profile-amendment.v0",
                             prior_profile_commitment, new_profile_commitment, escrow_ref }
amendment_cc             = sha256(JCS(amendment))
authorization (party)    = { party, signed_digest, pubkey }        # signed_digest MUST == amendment_cc
```

`JCS` is canonical JSON (sorted keys, no whitespace); `sha256` over its UTF-8 bytes — identical to
companion-envelope-v0.

## Rule

A change from profile A to profile B is a **permitted** transition iff, together:

1. **Binding** — an amendment exists whose declared `prior_profile_commitment` and `new_profile_commitment`
   equal the recomputed A and B commitments, and whose `escrow_ref` equals this task's `escrow_ref`. It binds
   *this* A→B for *this* task.
2. **Two-party authorization** — every required party (default `buyer`, `supplier`) has an authorization whose
   `signed_digest` is present AND equals `amendment_cc`. Both sides co-signed *this exact* amendment.

Otherwise `transition_status` is `"unresolved"` and `effective_profile_commitment` **fails closed** to
`prior_profile_commitment`: an unauthorized change never takes effect. `unresolved`, never a silent permit.

Three cases, mirroring the WG contract:

| case | meaning |
|---|---|
| A → A | no change; normal resolution |
| A → B, no valid amendment | unauthorized swap → `unresolved`, effective stays A (fail closed) |
| A → co-signed amendment → B | permitted transition, provenance independently checkable |

## Scope

This checks the **binding**, not signature cryptography: an authorization is *bound* iff its `signed_digest`
equals `amendment_cc`, exactly as companion-envelope checks `content_address == verdict_core_cc`. ML-DSA /
ECDSA validity of each party's signature rides the separate signature lane and is intentionally not
recomputed here. A downstream consumer composes both: the binding (this suite) and signature validity.

## Vectors

Eight, in `profile-amendment-v0.vectors.json` — two permitted, six refused, one negative per predicate:

- `permitted` — A→B bound, both co-sign → permitted, effective = B
- `permitted-distinct-pubkey` — same binding, different buyer pubkey, same `signed_digest` → still permitted
  (the pubkey value must not move the verdict; shape not value)
- `bare-swap-no-amendment` — B differs from A, no amendment → unresolved, effective = A (the core attack)
- `buyer-only` / `supplier-only` — one-sided authorization → unresolved
- `wrong-prior` — amendment chains from a different prior → does not bind this A → unresolved
- `wrong-escrow` — amendment for another `escrow_ref` → cannot authorize this task → unresolved
- `auth-names-wrong-digest` — signatures over some other amendment → not authorized → unresolved

Reproduced byte-for-byte by both `amendment_gate.py` (Python) and `profile-amendment-v0.reference.mjs`
(bun/node, an independent `jcs`); each reds on a refuted vector.
