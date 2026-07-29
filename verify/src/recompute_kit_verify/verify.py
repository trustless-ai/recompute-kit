"""Offline verifier for recompute-kit receipts — recompute the root yourself, trust no one.

Accepts either a `receiptos.evidence_capsule.v0` or a `recompute-kit.conformance_proof_object.v0`
(which embeds the capsule). Recomputes `receipt_root` locally and reads the capsule's own
`verifier_result` verbatim — never inferring the verdict from the root match.

Tri-state (couldn't-check is its own verdict, never a silent pass):
  verified-good  — root recomputes AND the carried conformance verdict is ok
  verified-bad   — root mismatches (tampered/mis-derived) OR the carried verdict is rejected
  UNVERIFIABLE   — not parseable, no capsule to recompute, or no stored root / verdict to check
"""
from .canon import receipt_root

CAPSULE_SCHEMA = "receiptos.evidence_capsule.v0"
OBJECT_SCHEMA = "recompute-kit.conformance_proof_object.v0"

GOOD, BAD, UNVERIFIABLE = "verified-good", "verified-bad", "UNVERIFIABLE"


def _extract(obj):
    """Return (capsule, stored_root, verifier_result) for a capsule or a portable object."""
    schema = obj.get("schema")
    if schema == OBJECT_SCHEMA:
        cap = obj.get("evidence_capsule")
        return cap, obj.get("receipt_root"), (obj.get("provenance_summary") or {}).get("verifier_result")
    if schema == CAPSULE_SCHEMA:
        return obj, (obj.get("receipt_root") or {}).get("stored"), obj.get("verifier_result")
    return None, None, None


def _signature(obj) -> dict:
    """Signature lane — inert until receipts are signed (producer-side). Structured so a signed
    receipt just fills this in without changing the caller. Integrity today rests on receipt_root."""
    sig = obj.get("signature")
    if not sig:
        return {"present": False, "note": "integrity-bound by receipt_root; unsigned in this version"}
    return {"present": True, "note": "signature present — verification not enabled in this build"}


def verify_object(obj) -> dict:
    if not isinstance(obj, dict):
        return {"status": UNVERIFIABLE, "reason": "not a JSON object"}
    cap, stored, vres = _extract(obj)
    if not isinstance(cap, dict) or cap.get("schema") != CAPSULE_SCHEMA:
        return {"status": UNVERIFIABLE, "reason": "no receiptos.evidence_capsule.v0 to recompute"}

    computed = receipt_root(cap)
    if stored is None:
        return {"status": UNVERIFIABLE, "reason": "no stored receipt_root to check integrity against",
                "root_computed": computed}
    if stored != computed:
        return {"status": BAD, "reason": "receipt_root mismatch — tampered or mis-derived",
                "root_stored": stored, "root_computed": computed, "verifier_result": vres,
                "signature": _signature(obj)}
    if not isinstance(vres, dict):
        return {"status": UNVERIFIABLE, "reason": "root matches but no verifier_result carried",
                "root": computed}

    ok = bool(vres.get("ok"))
    return {
        "status": GOOD if ok else BAD,
        "reason": ("root recomputes + conformance verdict carried verbatim (ok)" if ok
                   else "root recomputes, but the carried conformance verdict is REJECTED"),
        "root": computed,
        "verifier_result": vres,
        "signature": _signature(obj),
    }
