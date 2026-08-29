#!/usr/bin/env python3
"""provenance-anchor.v0 — build-first origination gate (verdict logic).

SCOPE — deterministic verdict logic. Resolution is a MODEL INPUT (companion resolve_anchor.py produces the
real one); the graded suite stays byte-deterministic. It proves a WITNESSED temporal + existence claim and
nothing about semantics.

A record DECLARES its `claim`: `origination` (the anchor tx must COMMIT the digest of a canonical
anchor-binding.v0 object naming proposal+artifact) or `pre_existence` (only witnessed precedence). A PASS
carries its claim — PASS:origination | PASS:pre_existence — so pre-existence can never read as origination
(@zexoverz/Faisal: a free-standing anchor that merely exists before a thread proves pre-existence, not
origination — moving the 8299 tx into an 8373 record must NOT pass).

Facts, each independently established:
  1. content identity   — the object exists and its bytes/hash are stable.
  2. existence witness   — an INDEPENDENT observation of when the object was public; NOT its self-reported
                           time. On-chain tx: intrinsic (consensus block). Git commit: a SEPARATE witness.
  3. anchor subject binding — the anchor witness references THIS anchor (git: commit hash in the commitment).
  4. thread subject binding — the thread witness is THIS proposal's opening boundary: a forge_event in the
                           proposal's CANONICAL repo (erc->ethereum/ERCs, eip->ethereum/EIPs, repo-native->
                           its own repo) that ADDs the proposal's EXACT-CASE spec path.
  5. anchor->proposal/artifact binding (ORIGINATION only) — the tx commits the anchor-binding digest, the
                           binding is coherent with the scored proposal, and (if declared) signer==originator.
  6. witnessed precedence — the witnessed anchor time strictly precedes the witnessed THREAD-OPEN time.

The gate checks resolution/anchor coherence, fails closed on a non-object resolution, rejects bool where an
int is required, and rejects an empty corpus. If any fact is unmet the verdict is UNVERIFIABLE or FAIL.

Verdict (closed enumeration, never a silent green):
  PASS:origination | PASS:pre_existence
  FAIL:malformed_record | missing_anchor | malformed_anchor | missing_thread_open | malformed_thread_open
      | missing_proposal | malformed_proposal | malformed_claim | malformed_binding | binding_incoherent
      | anchor_not_found | anchor_not_bound | signer_mismatch | postdates_thread
  UNVERIFIABLE:no_publication_witness | witness_unresolved | witness_not_bound | incoherent_resolution
      | thread_unwitnessed | thread_not_bound | anchor_bound_unresolved | pruned_history | rpc_unreachable
      | source_unavailable

Usage: python3 provenance_gate.py provenance-anchor-v0.vectors.json
Exit 0 iff every case reproduces its expected verdict, else 1.
"""
from __future__ import annotations
import json, os, re, sys
import anchor_binding as ab  # the canonical proposal+artifact binding the anchor must commit

TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ANCHOR_WITNESS_KINDS = {"onchain_commitment", "transparency_log", "forge_event"}
THREAD_WITNESS_KINDS = {"onchain_commitment", "forge_event"}
PROPOSAL_KINDS = {"erc", "eip", "repo"}
# A proposal opens in exactly one canonical repository — a forge_event from any other repo that merely adds
# the same path cannot be the opening boundary (repo names compared case-insensitively, as GitHub does).
# erc/eip have fixed canonical repos; a generic `repo`-native standard IS defined by its own repo.
CANONICAL_REPO = {"erc": "ethereum/ERCs", "eip": "ethereum/EIPs"}


def canonical_repo(proposal):
    kind = proposal.get("kind")
    if kind in CANONICAL_REPO:
        return CANONICAL_REPO[kind]
    if kind == "repo":
        return proposal.get("repo")   # a repo-native standard is self-defining: no external repo to spoof
    return None
CONTENT_UNAVAILABLE = {"unavailable_pruned": "pruned_history",
                       "unavailable_rpc": "rpc_unreachable",
                       "unavailable_source": "source_unavailable"}


def _is_int(x):
    # bool is a subclass of int — reject it, or True/False would satisfy chain_id / timestamps.
    return isinstance(x, int) and not isinstance(x, bool)


def _well_formed_witness(w, kinds):
    if not isinstance(w, dict) or w.get("kind") not in kinds:
        return "witness_kind"
    if w["kind"] == "onchain_commitment":
        if not (_is_int(w.get("chain_id")) and isinstance(w.get("tx"), str) and TX_RE.match(w["tx"])):
            return "witness_locator"
    if w["kind"] == "forge_event":
        if not (isinstance(w.get("repo"), str) and REPO_RE.match(w["repo"]) and _is_int(w.get("pr"))):
            return "witness_locator"
    return None


def well_formed_anchor(anchor):
    if not isinstance(anchor, dict):
        return "not_an_object"
    kind = anchor.get("kind")
    if kind == "onchain_tx":
        if not _is_int(anchor.get("chain_id")):
            return "chain_id"
        if not (isinstance(anchor.get("tx"), str) and TX_RE.match(anchor["tx"])):
            return "tx"
        return None
    if kind == "git_commit":
        if not (isinstance(anchor.get("repo"), str) and REPO_RE.match(anchor["repo"])):
            return "repo"
        if not (isinstance(anchor.get("commit"), str) and SHA_RE.match(anchor["commit"])):
            return "commit"
        w = anchor.get("witness")
        if w is not None:
            return _well_formed_witness(w, ANCHOR_WITNESS_KINDS)
        return None
    return "kind"


def well_formed_thread(thread_open):
    if not isinstance(thread_open, dict):
        return "not_an_object"
    return _well_formed_witness(thread_open.get("witness"), THREAD_WITNESS_KINDS)


def well_formed_proposal(proposal):
    if not isinstance(proposal, dict):
        return "not_an_object"
    if proposal.get("kind") not in PROPOSAL_KINDS:
        return "kind"
    if not _is_int(proposal.get("id")):
        return "id"
    if proposal.get("kind") == "repo":       # a repo-native proposal carries its own canonical repo
        if not (isinstance(proposal.get("repo"), str) and REPO_RE.match(proposal["repo"])):
            return "repo"
    return None


def anchor_expects_witness(anchor):
    if anchor.get("kind") == "onchain_tx":
        return True                       # intrinsic — the block is the witness
    if anchor.get("kind") == "git_commit":
        return bool(anchor.get("witness"))  # only if a separate witness is declared
    return False


def verdict(record, resolution):
    if not isinstance(record, dict):
        return "FAIL:malformed_record"
    anchor = record.get("anchor")
    if anchor is None:
        return "FAIL:missing_anchor"
    if well_formed_anchor(anchor) is not None:
        return "FAIL:malformed_anchor"
    thread_open = record.get("thread_open")
    if thread_open is None:
        return "FAIL:missing_thread_open"
    if well_formed_thread(thread_open) is not None:
        return "FAIL:malformed_thread_open"
    # The subject being scored — the thread witness must bind to THIS proposal, or a caller could
    # point at a later, unrelated PR and manufacture precedence.
    proposal = record.get("proposal")
    if proposal is None:
        return "FAIL:missing_proposal"
    if well_formed_proposal(proposal) is not None:
        return "FAIL:malformed_proposal"

    # The claim being made. `origination` requires the anchor to COMMIT a canonical proposal+artifact
    # binding; `pre_existence` requires only witnessed precedence. The record MUST say which, so a PASS
    # never means more than was claimed — this is what structurally prevents the origination overclaim
    # (@zexoverz/Faisal: a free-standing anchor proves pre-existence, not origination).
    claim = record.get("claim")
    if claim not in ("origination", "pre_existence"):
        return "FAIL:malformed_claim"
    if claim == "origination":
        binding = anchor.get("binding")
        if ab.validate(binding) is not None:
            return "FAIL:malformed_binding"
        # The binding's proposal must be exactly the proposal being scored, in its canonical repo.
        canon = canonical_repo(proposal)
        if binding["proposal"] != {"kind": proposal["kind"], "id": proposal["id"], "repo": canon}:
            return "FAIL:binding_incoherent"

    # Fail closed on a non-object resolution (never crash, never pass).
    if not isinstance(resolution, dict):
        return "UNVERIFIABLE:no_publication_witness"
    ares = resolution.get("anchor")
    tres = resolution.get("thread")
    if not isinstance(ares, dict):
        return "UNVERIFIABLE:no_publication_witness"

    # Fact 1 — content identity.
    content = ares.get("content")
    if content == "not_found":
        return "FAIL:anchor_not_found"
    if content in CONTENT_UNAVAILABLE:
        return f"UNVERIFIABLE:{CONTENT_UNAVAILABLE[content]}"
    if content != "confirmed":
        return "UNVERIFIABLE:rpc_unreachable"

    # Coherence — the resolution must not claim more than the anchor declares.
    if bool(ares.get("witness_declared")) != anchor_expects_witness(anchor):
        return "UNVERIFIABLE:incoherent_resolution"

    # Fact 2 — existence witness.
    if not ares.get("witness_declared"):
        return "UNVERIFIABLE:no_publication_witness"
    awts = ares.get("witnessed_ts")
    if not _is_int(awts):
        return "UNVERIFIABLE:witness_unresolved"

    # Fact 3 — subject binding: the witness must reference THIS subject.
    if not ares.get("subject_bound"):
        return "UNVERIFIABLE:witness_not_bound"

    # Fact 4 — the thread-open boundary must itself be witnessed.
    if not isinstance(tres, dict) or not tres.get("witnessed"):
        return "UNVERIFIABLE:thread_unwitnessed"
    twts = tres.get("witnessed_ts")
    if not _is_int(twts):
        return "UNVERIFIABLE:thread_unwitnessed"

    # Fact 4 — thread subject binding. The witness must sit in the proposal's CANONICAL repository, or a
    # spoof repo that adds the same path could impersonate the opening — regardless of what the resolution
    # claims. Enforce the repo binding here (deterministic coherence) as well as in the live resolver.
    tw = thread_open.get("witness", {})
    if tw.get("kind") == "forge_event":
        canon = canonical_repo(proposal)
        if not canon or str(tw.get("repo", "")).lower() != canon.lower():
            return "UNVERIFIABLE:thread_not_bound"
    if not tres.get("subject_bound"):
        return "UNVERIFIABLE:thread_not_bound"

    # Fact 5 — anchor → proposal/artifact binding (ORIGINATION ONLY). The anchor transaction must commit
    # the digest of the canonical binding object (proposal + implementation artifact). A free-standing tx
    # that commits arbitrary bytes (e.g. sha256("hello")) is pre-existence, not origination.
    if claim == "origination":
        bound = ares.get("bound")
        if bound is None:
            return "UNVERIFIABLE:anchor_bound_unresolved"
        if not bound:
            return "FAIL:anchor_not_bound"
        # If an originator is declared, the anchor signer must be that identity.
        originator = anchor.get("originator")
        if originator is not None:
            signer = ares.get("signer")
            if not isinstance(signer, str) or signer.lower() != str(originator).lower():
                return "FAIL:signer_mismatch"

    # Witnessed precedence — both sides are independently witnessed AND bound to their subjects.
    if awts >= twts:
        return "FAIL:postdates_thread"
    # A PASS carries the claim it satisfies — never bare "PASS", so pre-existence can't read as origination.
    return f"PASS:{claim}"


def run(path):
    fx = json.load(open(path, encoding="utf-8"))
    cases = fx["cases"]
    if not isinstance(cases, list) or len(cases) == 0:
        print("0 cases — an empty corpus is not a pass")   # reject: fails==0 must require cases>0
        return False
    fails = 0
    for c in cases:
        got = verdict(c["record"], c.get("resolution"))
        exp = c["expected"]
        ok = got == exp
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['name']:<34} -> {got:<38} (want {exp})")
    print(f"{len(cases) - fails}/{len(cases)} cases reproduced")
    return fails == 0


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "provenance-anchor-v0.vectors.json")
    sys.exit(0 if run(arg) else 1)
