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

Deterministic and non-retroactive per Pavlo's spec: `deadline_policy_commitment` is a content-hash
of exactly {policy_version, request_class, delta_seconds} -- recomputable by any third party from
the SLA table alone, and bound into the admission record at accepted_at. If the SLA table is edited
later, a PRIOR admission still validates against the deadline_policy_commitment it was bound to, not
against whatever the live table says now (see PREV_POLICY_SLA_TABLE / vector 6 below) -- exactly the
same non-retroactivity discipline the core's own authority mode already enforces for epoch transitions.
"""
import hashlib, json, sys

# request_class bucketing -- reuses the real, live IRREVERSIBLE_ARTIFACT_TYPES set
# (services/proof_signing.py) rather than inventing a new dimension.
IRREVERSIBLE_ARTIFACT_TYPES = frozenset({"onchain_action", "trade", "sanctions_screening"})
REVERSIBLE_ARTIFACT_TYPES = frozenset({
    "code_diff", "patch", "shell_command", "plan", "config_change",
    "analysis", "agent_output", "general",
})
ALL_KNOWN_ARTIFACT_TYPES = IRREVERSIBLE_ARTIFACT_TYPES | REVERSIBLE_ARTIFACT_TYPES


def request_class_of(artifact_type: str) -> str | None:
    if artifact_type in IRREVERSIBLE_ARTIFACT_TYPES:
        return "long"
    if artifact_type in REVERSIBLE_ARTIFACT_TYPES:
        return "short"
    return None  # unknown artifact_type -- not in either bucket


# The pinned SLA table for policy_version invinoveritas.review.v5. "short" keeps the original
# proposed +60s (generous over typical sub-10s LLM latency for a reversible artifact); "long"
# is 180s -- irreversible-class review can trigger the reversibility_gate's extra confidence-floor
# check (routes/inference.py), which is real additional processing, not just a bigger number
# picked for its own sake.
POLICY_SLA_TABLE = {
    "invinoveritas.review.v5": {"short": 60, "long": 180},
}

# A deliberately-frozen PRIOR table, used only by vector 6 (non-retroactivity) to prove an old
# admission still resolves against the deadline_policy_commitment it was bound to, not the live
# table above -- simulates "the SLA table got edited later."
PREV_POLICY_SLA_TABLE = {
    "invinoveritas.review.v5": {"short": 45, "long": 120},
}


def _h(obj) -> str:
    return "dpc:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def compute_deadline_policy_commitment(policy_version: str, request_class: str, table=None) -> str | None:
    table = table if table is not None else POLICY_SLA_TABLE
    delta = (table.get(policy_version) or {}).get(request_class)
    if delta is None:
        return None
    return _h({"policy_version": policy_version, "request_class": request_class, "delta_seconds": delta})


def derive(policy_version: str, request_class: str, accepted_at: int, table=None):
    table = table if table is not None else POLICY_SLA_TABLE
    delta = (table.get(policy_version) or {}).get(request_class)
    if delta is None:
        return None, None
    commitment = compute_deadline_policy_commitment(policy_version, request_class, table)
    return accepted_at + delta, commitment


# -- the pre-validator itself --------------------------------------------------------------------
# Recomputes Δ from the record's OWN bound {policy_version, request_class, deadline_policy_commitment,
# accepted_at} and checks it against the record's OWN supplied response_deadline -- never against
# whatever POLICY_SLA_TABLE says *right now*, except to confirm the bound commitment IS derivable
# from some real table entry (current or, for vector 6, an explicitly-supplied historical one).
def validate_deadline(record: dict, table=None) -> tuple[str, list[str]]:
    table = table if table is not None else POLICY_SLA_TABLE
    policy_version = record.get("policy_version")
    request_class = record.get("request_class")
    accepted_at = record.get("accepted_at")
    supplied_deadline = record.get("response_deadline")
    supplied_commitment = record.get("deadline_policy_commitment")

    if request_class not in ("short", "long"):
        return "unknown_request_class", [f"request_class={request_class!r}_not_in_(short,long)"]

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

    derived_deadline, derived_commitment = derive(policy_version, request_class, accepted_at, table)
    if derived_deadline is None:
        return "unknown_request_class", [f"no_sla_table_entry_for_({policy_version!r},{request_class!r})"]

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
        "recomputed_from_declared_policy_version+request_class+accepted_at",
    ]


def check(case: dict):
    table = PREV_POLICY_SLA_TABLE if case.get("_use_prev_table") else POLICY_SLA_TABLE
    v, notes = validate_deadline(case["record"], table)
    return v == case["expected_verdict"], v, notes


if __name__ == "__main__":
    fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "deadline_vectors.json"))
    fails = 0
    for c in fx["cases"]:
        ok, v, notes = check(c)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<55} -> {v:<32} (want {c['expected_verdict']})  · {' · '.join(notes)}")
    print(f"\n{len(fx['cases']) - fails}/{len(fx['cases'])} cases reproduced" + ("" if not fails else "  <- MISMATCH"))
    sys.exit(1 if fails else 0)
