#!/usr/bin/env python3
"""crc.claim.v0 core for the crc/* recipes — gate, JCS, claim_id, lift.v0.

Ported from trustless-ai/cross-reference-console@a82f8f1 reference/claim_id.py
(the conformance boundary the first live 2x1 edge was built against) plus the
watcher's lift.v0 (proven byte-compatible with the hand-minted /ledger #236
claim). Stdlib only.

The pre-hash gate is strict BY DESIGN: a structurally incomplete, extended, or
duplicated-member input is rejected — it never receives a claim_id.
"""
import json, hashlib, re, datetime

FIELDS = ["schema", "profile_id", "policy_version", "artifact_hash",
          "artifact_type", "claim_body", "source_class", "verifier_profile",
          "as_of", "claimant"]
_STR_FIELDS = ["schema", "profile_id", "policy_version", "artifact_hash",
               "artifact_type", "source_class", "verifier_profile", "as_of"]
_AS_OF_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_HASH_RE = re.compile(r"[0-9a-f]{64}")
_UINT256_MAX = 2**256 - 1


def _reject_duplicate_pairs(pairs):
    """JCS is only defined over unique members; a parser that silently keeps the
    last member lets two different byte-streams canonicalize identically.
    Detected at parse time — on the parsed object the evidence is gone."""
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError(f"duplicate JSON member: {k!r}")
        obj[k] = v
    return obj


def loads_strict(text: str):
    """Parse JSON text rejecting duplicate members at any depth."""
    return json.loads(text, object_pairs_hook=_reject_duplicate_pairs)


def validate(preimage: dict) -> None:
    """The pre-hash gate. Raise ValueError unless an exact, well-typed crc.claim.v0."""
    if not isinstance(preimage, dict):
        raise ValueError("ClaimPreimage must be a JSON object")
    keys = set(preimage)
    required = set(FIELDS)
    missing = sorted(required - keys)
    extra = sorted(keys - required)
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    if extra:
        raise ValueError(f"unknown fields (not in crc.claim.v0): {extra}")
    if preimage["schema"] != "crc.claim.v0":
        raise ValueError("schema must be exactly 'crc.claim.v0'")
    for k in _STR_FIELDS:
        if not isinstance(preimage[k], str) or preimage[k] == "":
            raise ValueError(f"{k} must be a non-empty string")
    if not (preimage["claim_body"] is None or isinstance(preimage["claim_body"], str)):
        raise ValueError("claim_body must be a string or null")
    if not _HASH_RE.fullmatch(preimage["artifact_hash"]):
        raise ValueError("artifact_hash must match ^[0-9a-f]{64}$ (bare lowercase hex)")
    if isinstance(preimage["claimant"], bool) or not isinstance(preimage["claimant"], int):
        raise ValueError("claimant must be an integer (ERC-8004 token id)")
    if not (0 <= preimage["claimant"] <= _UINT256_MAX):
        raise ValueError("claimant must be in uint256 range [0, 2^256)")
    if not _AS_OF_RE.fullmatch(preimage["as_of"]):
        raise ValueError("as_of must be RFC3339 UTC 'YYYY-MM-DDTHH:MM:SSZ'")
    datetime.datetime.strptime(preimage["as_of"], "%Y-%m-%dT%H:%M:%SZ")


def jcs(obj) -> str:
    """JCS serialization for string/int/null-leaf objects (crc.claim.v0 territory)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical(preimage: dict) -> bytes:
    validate(preimage)
    return jcs({k: preimage[k] for k in FIELDS}).encode("utf-8")


def claim_id(preimage: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(preimage)).hexdigest()


def rfc3339(unix) -> str:
    return datetime.datetime.fromtimestamp(int(unix), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lift_v0(lc: dict, claimant: int = 54848) -> dict:
    """invinoveritas.verdict_proof.v1 → crc.claim.v0 ClaimPreimage. Deterministic:
    as_of is the verdict's own verified_at instant; claimant is the issuing
    verifier's ERC-8004 id. Lifting /ledger #236 derives the hand-minted
    sha256:df1a6bfe… byte-for-byte — one rule, no special cases."""
    return {
        "schema": "crc.claim.v0",
        "profile_id": lc["platform"] + ".review",
        "policy_version": lc["policy_version"],
        "artifact_hash": lc["decision_ref"].removeprefix("sha256:"),
        "artifact_type": "review_verdict",
        "claim_body": lc["verdict"],
        "source_class": lc["source_class"],
        "verifier_profile": "attestation/" + lc["platform"],
        "as_of": rfc3339(lc["verified_at"]),
        "claimant": claimant,
    }
