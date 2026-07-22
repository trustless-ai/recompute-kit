"""receiptos-c14n-v0 canonicalization + the evidence-capsule and portable-proof-object builders.

Shared by the gate, the CLI, and the exporter so every path produces byte-identical roots.

The portable-proof-object builder is **deterministic with respect to the capsule**, achieved ONLY by
deterministic serialization + deterministic projection of already-pinned capsule fields — never by
reinterpreting timestamps or references. Fields with no real referent or no v0-defined capsule relation
(`anchor_ref`, `created_at`, `replay_ref`, `source_evidence_ref`) are emitted as `null`, NOT synthesized
from `runner`/`ran_at`. No export-time wall-clock enters the object, so re-exporting a given capsule is
byte-identical (idempotent re-import), and an importer fails closed only on genuinely different content
for the same proof root. Contract:

    proof_object_id = "proofobj-" + receipt_root without "0x"
    proof_ref       = "receiptos://portable-proof-object/" + proof_object_id

Two separations kept explicit (Pavlo, 2026-07-22):
  - a matching receipt_root proves capsule IDENTITY + canonical integrity, NOT proof validity. This
    builder only binds/carries; the capsule's own `verifier_result` is preserved verbatim and the
    ReceiptOS verification contract is applied separately by the verifier/importer.
  - identity is root-derived (not a content hash of the whole envelope); a whole-object digest, if ever
    wanted, is an additive/separately-versioned field, not a change here.
"""
import json as _json
import hashlib


def jcs(obj) -> bytes:
    """RFC-8785-style canonical JSON bytes (sorted keys, compact, UTF-8)."""
    return _json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def receipt_root(receipt: dict) -> str:
    """receiptos-c14n-v0: "0x" + sha256(JCS(receipt \\ {anchor, receipt_root}))."""
    content = {k: v for k, v in receipt.items() if k not in ("anchor", "receipt_root")}
    return "0x" + hashlib.sha256(jcs(content)).hexdigest()


def build_capsule(run: dict, candidate: dict) -> dict:
    """Mint a receiptos.evidence_capsule.v0 from a graded run."""
    ok = bool(run.get("pass"))
    rep, tot = run.get("reproduced"), run.get("total")
    receipt = {
        "schema": "receiptos.evidence_capsule.v0",
        "action": {
            "summary": f"Conformance grade: {candidate.get('label', 'MCP')} against {run.get('profile')}",
            "source_fields": ["candidate.endpoint", "capsule.suite.vectors_sha256"],
        },
        "evidence": {
            "summary": (f"{rep}/{tot} golden vectors reproduced — the MCP's output matched the "
                        "recompute-kit's independent derivation from public rules"
                        if ok else f"{rep}/{tot} reproduced — the MCP did not build what the rules dictate"),
            "source_fields": ["capsule.results[].expected", "capsule.results[].got"],
            "status": "present",
        },
        "verifier_result": {"ok": ok, "status": "verified" if ok else "rejected"},
        "capsule": {
            "profile": run.get("profile"),
            "suite": {"vectors_sha256": run.get("vectors_sha256"),
                      "spec_sha256": run.get("spec_sha256"),
                      "recompute": run.get("recompute")},
            "candidate": candidate,
            "verdict": {"pass": ok, "reproduced": rep, "total": tot},
            "results": run.get("results", []),
        },
        "anchor": {"ran_at": run.get("ran_at"), "runner": run.get("runner", "recompute-kit/conformance-suite")},
    }
    root = receipt_root(receipt)
    receipt["receipt_root"] = {"stored": root, "computed": root, "match": True, "status": "verified",
                               "derivation": "receiptos-c14n-v0 — 0x + sha256(JCS(receipt \\ {anchor, receipt_root}))"}
    return receipt


DEFAULT_PROJECT_REFS = ["trustless-ai/recompute-kit", "Echo-Merlini/agent-mcp-catalog"]


def build_portable_object(capsule: dict, *, proof_system: str = "recompute-kit/conformance",
                          project_refs=None, relation_type: str = "external-conformance") -> dict:
    """Wrap a receiptos.evidence_capsule.v0 in a portable_proof_object.v0.

    Pure function of the capsule — no wall-clock, so re-export is byte-identical. Fails closed if the
    capsule's stored root does not recompute (never trusts the carried value blindly).
    """
    if not isinstance(capsule, dict) or capsule.get("schema") != "receiptos.evidence_capsule.v0":
        raise ValueError("expected a receiptos.evidence_capsule.v0 object")
    computed = receipt_root(capsule)
    stored = (capsule.get("receipt_root") or {}).get("stored")
    if stored is not None and stored != computed:
        raise ValueError(f"capsule receipt_root mismatch: stored {stored} != recomputed {computed}")
    root = computed

    proof_object_id = "proofobj-" + root[2:]
    proof_ref = "receiptos://portable-proof-object/" + proof_object_id

    anchor = capsule.get("anchor") or {}
    ran_at = anchor.get("ran_at")
    runner = anchor.get("runner", "recompute-kit/conformance-suite")
    cap = capsule.get("capsule") or {}
    suite = cap.get("suite") or {}
    verdict = cap.get("verdict") or {}

    return {
        # NOT receiptos.portable_proof_object.v0 — that v0 is welded to the Stealth/HandoffEvidence
        # producer (fixed proof_system=ReceiptOS, relation_type=imported, required producer/metadata/
        # created_at/source_evidence_ref) and an honest external conformance exporter cannot fill it
        # without synthesizing values (which we refuse). This is our own external-conformance object
        # whose IDENTITY lives in the receiptos namespace (proof_object_id/proof_ref/receipt_root are the
        # audited, interop-proven chain), pending a canonical ReceiptOS external/conformance profile we'll
        # adopt once pinned.
        "schema": "recompute-kit.conformance_proof_object.v0",
        "proof_object_id": proof_object_id,
        "proof_ref": proof_ref,
        "proof_system": proof_system,
        "receipt_root": root,
        # anchor_ref / created_at / replay_ref / source_evidence_ref: null unless a REAL anchor artifact
        # or an explicit v0-defined capsule relation exists — never synthesized from runner/ran_at, and
        # never export-time wall-clock (keeps re-export byte-identical without reinterpreting semantics).
        "replay_ref": None,
        "anchor_ref": None,
        "created_at": None,
        "relation_type": relation_type,
        "project_refs": list(project_refs) if project_refs is not None else list(DEFAULT_PROJECT_REFS),
        "source_evidence_ref": None,
        "evidence_capsule": capsule,
        # deterministic projection of already-pinned capsule fields only; the verifier verdict is the
        # capsule's own, carried VERBATIM ({ ok, status }) — never a projected string, never inferred
        # from the receipt_root match.
        "provenance_summary": {
            "verifier_result": capsule.get("verifier_result"),
            "pass": verdict.get("pass"),
            "reproduced": verdict.get("reproduced"),
            "total": verdict.get("total"),
            "spec_sha256": suite.get("spec_sha256"),
            "vectors_sha256": suite.get("vectors_sha256"),
            "recompute": suite.get("recompute"),
            "runner": runner,
            "ran_at": ran_at,
        },
    }
