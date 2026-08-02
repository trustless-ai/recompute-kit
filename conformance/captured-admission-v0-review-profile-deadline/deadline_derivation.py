#!/usr/bin/env python3
"""Profile-owned pre-validator for response_deadline, per Merlini/Pavlo's fix (trustless-ai,
2026-08-02): "the deadline derivation belongs in Fede's profile-owned pre-validator... A profile-
owned pre-validator should recompute Δ from the pinned policy table before the record reaches the
shared obligation checker." This does NOT touch ../captured-admission-v0/admission_check.py --
it's a separate, additional check that runs on the admission record before/alongside the core.

response_deadline = accepted_at + Δ(policy_version, request_class)

`request_class` is NOT a new field invented for this profile -- it's our real, live `artifact_type`
(core/models.py, 11-valued Literal), bucketed into exactly the two classes IRREVERSIBLE_ARTIFACT_TYPES
already distinguishes in production (services/proof_signing.py, S216): the irreversible-class
artifacts (trade/onchain_action/sanctions_screening) already get a stricter reversibility_gate and a
vantage_limitation note than the reversible ones -- reusing that same real distinction here rather
than adding a second, unrelated axis is the honest version of "recomputable from data already public."

v0.2 (2026-08-02, Pavlo's second review, correcting v0.1 which was pulled out of PR #6 entirely
per his "don't stack this on the frozen baseline" fix): three real corrections, not cosmetic --

1. FULL-WIDTH sha256, not truncated. v0.1's `_h()` truncated to 64 bits (hexdigest()[:16]) and the
   README overclaimed it as "real cryptographic evidence" a coincidence "can't" fool -- a 64-bit
   truncation has meaningful collision risk and must never be called unfoolable. Fixed: full 256-bit
   hex digest, no truncation, no overclaiming beyond what the width actually buys.
2. `unknown_policy_version` is now DISTINCT from `unknown_request_class`. v0.1 collapsed "this
   policy_version was never defined" and "this request_class isn't short/long" into the same
   verdict -- two structurally different failures (an unrecognized policy identity vs. an
   unrecognized bucket within a real policy) that a third party auditing a rejected record needs
   to tell apart.
3. ONE immutable, append-only table keyed by policy_version -- not two separate tables ("current"
   vs "prev") the caller picks between. v0.1's real bug: both the old and new delta values reused
   the SAME policy_version string ("invinoveritas.review.v5"), which makes policy_version silently
   mutable and leaves "which table resolves an old record" outside the record entirely -- exactly
   what Pavlo's non-retroactivity point was about. Fixed the honest way, using the SAME discipline
   our own live REVIEW_POLICY_VERSION already follows (services/proof_signing.py: "bump this when
   the review contract/rubric changes... a past decision_ref always recomputes correctly against
   the rubric that was actually in force"): an SLA-delta change is a rubric change, so it gets its
   own new policy_version, appended to the SAME table, never overwriting the old entry. A record
   declaring an old policy_version is looked up under THAT key, forever -- there is no "current
   table" concept to accidentally apply to it. `invinoveritas.review.v4` here is used as the
   illustrative prior version (matching the REAL v2/v3/v4/v5 progression already documented in
   proof_signing.py) -- v4 itself never had a real SLA table in production; this is a proposed
   mechanism demonstration, not a historical record.
"""
import hashlib, json, sys

# request_class bucketing -- reuses the real, live IRREVERSIBLE_ARTIFACT_TYPES set
# (services/proof_signing.py) rather than inventing a new dimension.
IRREVERSIBLE_ARTIFACT_TYPES = frozenset({"onchain_action", "trade", "sanctions_screening"})
REVERSIBLE_ARTIFACT_TYPES = frozenset({
    "code_diff", "patch", "shell_command", "plan", "config_change",
    "analysis", "agent_output", "general",
})


def request_class_of(artifact_type: str) -> str | None:
    if artifact_type in IRREVERSIBLE_ARTIFACT_TYPES:
        return "long"
    if artifact_type in REVERSIBLE_ARTIFACT_TYPES:
        return "short"
    return None  # unknown artifact_type -- not in either bucket


# ONE immutable, append-only table, keyed by policy_version. A version's entry is never edited or
# removed once real records reference it -- an SLA-delta change mints a NEW policy_version (same
# discipline as REVIEW_POLICY_VERSION's own real v2->v3->v4->v5 bumps). There is no "current" vs
# "prior" table distinction at the API level -- callers always resolve by the record's OWN declared
# policy_version, which is what makes non-retroactivity structural rather than a convention.
POLICY_SLA_TABLE = {
    "invinoveritas.review.v4": {"short": 45, "long": 120},  # illustrative prior version -- see module docstring
    "invinoveritas.review.v5": {"short": 60, "long": 180},
}


def _h(obj) -> str:
    # full-width sha256, no truncation (v0.2 fix -- see module docstring point 1)
    return "dpc:sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compute_deadline_policy_commitment(policy_version: str, request_class: str) -> str | None:
    delta = (POLICY_SLA_TABLE.get(policy_version) or {}).get(request_class)
    if delta is None:
        return None
    return _h({"policy_version": policy_version, "request_class": request_class, "delta_seconds": delta})


def derive(policy_version: str, request_class: str, accepted_at: int):
    delta = (POLICY_SLA_TABLE.get(policy_version) or {}).get(request_class)
    if delta is None:
        return None, None
    return accepted_at + delta, compute_deadline_policy_commitment(policy_version, request_class)


# -- the pre-validator itself --------------------------------------------------------------------
# Recomputes Δ from the record's OWN bound {policy_version, request_class, deadline_policy_commitment,
# accepted_at} and checks it against the record's OWN supplied response_deadline. Always resolves by
# the record's declared policy_version against the ONE immutable table above -- never against "the
# current entry" as a separate concept, which is what makes an old record's validation independent
# of whatever the table's newest key happens to be.
def validate_deadline(record: dict) -> tuple[str, list[str]]:
    policy_version = record.get("policy_version")
    request_class = record.get("request_class")
    accepted_at = record.get("accepted_at")
    supplied_deadline = record.get("response_deadline")
    supplied_commitment = record.get("deadline_policy_commitment")

    if policy_version not in POLICY_SLA_TABLE:
        return "unknown_policy_version", [f"policy_version={policy_version!r}_not_in_sla_table"]

    if request_class not in POLICY_SLA_TABLE[policy_version]:
        return "unknown_request_class", [f"request_class={request_class!r}_not_defined_for_{policy_version!r}"]

    artifact_type = record.get("artifact_type")
    if artifact_type is not None:
        expected_class = request_class_of(artifact_type)
        if expected_class is None:
            return "unknown_request_class", [f"artifact_type={artifact_type!r}_not_in_any_known_bucket"]
        if expected_class != request_class:
            return "request_class_mismatch", [
                f"artifact_type={artifact_type!r}_buckets_to_{expected_class!r}",
                f"but_record_declares_request_class={request_class!r}",
                "request_class_changed_after_capture_or_admission_binding",
            ]

    derived_deadline, derived_commitment = derive(policy_version, request_class, accepted_at)

    if supplied_commitment != derived_commitment:
        return "deadline_policy_commitment_mismatch", [
            f"supplied={supplied_commitment!r}", f"derived={derived_commitment!r}",
            "commitment_not_recomputable_from_declared_inputs",
        ]

    if supplied_deadline != derived_deadline:
        return "deadline_not_derived", [
            f"supplied={supplied_deadline!r}", f"derived={derived_deadline!r}",
            f"accepted_at={accepted_at!r}+delta({policy_version!r},{request_class!r})",
        ]

    return "deadline_derivation_valid", [
        f"response_deadline={supplied_deadline!r}", f"deadline_policy_commitment={supplied_commitment!r}",
        "recomputed_from_declared_policy_version+request_class+accepted_at, resolved against the",
        f"immutable table entry for {policy_version!r} specifically -- not whatever entry is newest",
    ]


def check(case: dict):
    v, notes = validate_deadline(case["record"])
    return v == case["expected_verdict"], v, notes


if __name__ == "__main__":
    fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "deadline_vectors.json"))
    fails = 0
    for c in fx["cases"]:
        ok, v, notes = check(c)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<55} -> {v:<38} (want {c['expected_verdict']})  · {' · '.join(notes)}")
    print(f"\n{len(fx['cases']) - fails}/{len(fx['cases'])} cases reproduced" + ("" if not fails else "  <- MISMATCH"))
    sys.exit(1 if fails else 0)
