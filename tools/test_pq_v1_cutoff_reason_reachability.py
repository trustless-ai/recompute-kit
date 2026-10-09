#!/usr/bin/env python3
"""pq_key_binding.v1 — pins a REACHABILITY claim about the cutoff enforcer's reason vocabulary.

The claim, and why it is load-bearing rather than trivia:

    On the `resolved is None` branch, `rule == "no_in_force_binding"` is reachable ONLY when a
    revocation excluded a binding that would otherwise have governed.

That is what makes a separate `refuted_because: "authority_revoked"` field REDUNDANT today — the
reason already uniquely implies revocation, so a vector declaring the extra field could not have a
sibling case asserting its absence, and a mutant that always emitted it would survive. Adding it
would be a decorative expectation, the exact class `grade()` in cutoff_enforce.py now exists to
prevent.

So the claim is worth pinning rather than remembering. If someone later introduces a non-revocation
path to `no_in_force_binding` — a new activation rule, a chain shape this sweep does not yet cover —
the reason stops implying revocation, `t == R` genuinely becomes under-specified, and the
`authority_revoked` question (raised by @zexoverz on #18) has to be reopened. This test is how that
gets noticed instead of rediscovered.

Two halves, because a sweep that finds nothing proves nothing on its own:

  NEGATIVE  no chain WITHOUT revocations reaches no_in_force_binding
  POSITIVE  a chain WITH a revocation does reach it

The positive half is not decoration: without it, a probe that silently constructed invalid chains, or
called admit() wrongly, would report zero hits and pass while measuring nothing.

Run: python3 tools/test_pq_v1_cutoff_reason_reachability.py   -> exit 0 claim holds, 1 otherwise.
"""
import importlib.util
import itertools
import pathlib
import sys

SUITE = pathlib.Path(__file__).resolve().parent.parent / "conformance" / "pq-key-binding-v1"


def load_enforcer():
    spec = importlib.util.spec_from_file_location("cutoff_enforce_v1", SUITE / "cutoff_enforce.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def chains(max_bindings=2):
    """Well-formed chains over the parameters the resolution rule actually turns on: anchor time,
    optional delayed activation, and chain length. Chains that are MALFORMED by the profile's own
    definition (activated_at before binding_anchor_time) are skipped — admit() rejects those earlier
    as chain_malformed, so including them would probe a different branch and mask this one."""
    anchor_times = (100, 200)
    activations = (None, 50, 100, 200, 300)
    for n in range(1, max_bindings + 1):
        for anchors in itertools.product(anchor_times, repeat=n):
            for acts in itertools.product(activations, repeat=n):
                chain = []
                for i in range(n):
                    b = {
                        "name": f"b{i}",
                        "pq_pubkey": f"key-{i}",
                        "content_address": f"cc-{i}",
                        "binding_anchor_time": anchors[i],
                    }
                    if acts[i] is not None:
                        b["activated_at"] = acts[i]
                    chain.append(b)
                if any("activated_at" in b and b["activated_at"] < b["binding_anchor_time"] for b in chain):
                    continue
                yield chain


ANCHOR_TIMES_UNDER_TEST = (50, 99, 100, 150, 199, 200, 250, 300, 400)
FAR_FUTURE_CUTOFF = 10 ** 12  # keep the cutoff out of the way; this test is about resolution, not cutoff


def sweep(ce, apply_revocation):
    """Return (hits, probed). A hit is a verdict whose rule is no_in_force_binding."""
    hits, probed = [], 0
    for chain in chains():
        bindings = [dict(b) for b in chain]
        if apply_revocation:
            # Revoke the EARLIEST-anchored binding at a time inside the sweep's range, using the
            # profile's own apply_revocations() rather than hand-setting revoked_at, so the positive
            # control exercises the real path.
            target = min(bindings, key=lambda b: b["binding_anchor_time"])
            bindings = ce.apply_revocations(
                bindings,
                [{"revokes_content_address": target["content_address"], "revocation_anchor_time": 250}],
            )
        for at in ANCHOR_TIMES_UNDER_TEST:
            probed += 1
            verdict = ce.admit([dict(b) for b in bindings], FAR_FUTURE_CUTOFF,
                               {"anchor_time": at, "anchored": True})
            if verdict.get("rule") == "no_in_force_binding":
                hits.append((bindings, at, verdict))
    return hits, probed


def main():
    ce = load_enforcer()
    failures = []

    neg_hits, neg_probed = sweep(ce, apply_revocation=False)
    pos_hits, pos_probed = sweep(ce, apply_revocation=True)

    print(f"NEGATIVE  no revocations : {neg_probed} verdicts probed, "
          f"{len(neg_hits)} reached no_in_force_binding")
    print(f"POSITIVE  with revocation: {pos_probed} verdicts probed, "
          f"{len(pos_hits)} reached no_in_force_binding")

    if neg_hits:
        failures.append(
            f"no_in_force_binding is now reachable WITHOUT a revocation ({len(neg_hits)} cases). "
            "The reason no longer uniquely implies revocation, so t == R is genuinely "
            "under-specified and the authority_revoked question on #18 must be reopened."
        )
        chain, at, verdict = neg_hits[0]
        print(f"    first: anchor_time={at} chain={chain} -> {verdict}")

    if not pos_hits:
        failures.append(
            "the POSITIVE control found nothing: a revoked chain no longer reaches "
            "no_in_force_binding, so the negative sweep above is measuring nothing. "
            "Fix this probe before trusting either half."
        )

    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        return 1
    print("claim holds: on this branch no_in_force_binding implies revocation, and the probe can "
          "find it when a revocation is present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
