#!/usr/bin/env python3
"""provenance-anchor.v0 — build-first origination gate (verdict logic).

SCOPE — this is the DETERMINISTIC verdict logic of the provenance gate, NOT a chain fetcher. It verifies,
over the bytes it is given, that a proposal's origination anchor is present, well-formed, and that the
artifact was independently WITNESSED to exist before the discussion thread opened. Resolution is a MODEL
INPUT (`resolution`), matching pq-key-binding.v1/manifest — the companion `resolve_anchor.py` performs the
real fetch and PRODUCES a resolution; the graded suite stays byte-deterministic.

THREE SEPARATE FACTS (per @pipavlo82's review — timestamp authority is not uniform across anchor kinds):
  1. content identity   — the object exists and its bytes/hash are stable (recompute the tx / commit).
  2. existence witness  — an INDEPENDENT, externally-witnessed observation of WHEN the object was public.
                          NOT the object's own self-reported time.
  3. precedence         — the WITNESSED time is strictly before thread-open.

Why the split matters: an on-chain tx/deploy carries its own witness — the block timestamp is set by
consensus, not by the author. A bare git commit does NOT: author/committer dates are fields inside the
commit object and can be backdated; recomputing the commit hash proves the bytes and the CLAIMED time are
stable, never that the commit existed at that time. So a git anchor needs a SEPARATE witnessed-publication
fact — an on-chain commitment of the commit hash, a transparency-log entry, or a forge event that
references it. With no independent witness, precedence is self-reported provenance, which is
UNVERIFIABLE, not PASS.

What the gate still cannot prove, by construction: that the anchor is SEMANTICALLY the spec's primitive.
That is human review. The gate proves temporal witness + existence, nothing about semantics.

Verdict — three states, never a silent green:
  PASS                              content confirmed, an independent witness exists, witnessed time < thread.
  FAIL:missing_anchor               no anchor declared.
  FAIL:malformed_anchor             anchor does not parse for its kind.
  FAIL:anchor_not_found             content resolved to null (a fake reference).
  FAIL:postdates_thread             the WITNESSED time is at/after thread-open.
  UNVERIFIABLE:no_publication_witness   content is real but no independent witness of its publication time
                                        exists — a self-reported time is not a witness. (Bare git commit.)
  UNVERIFIABLE:witness_unresolved   a witness is declared but could not be independently resolved now.
  UNVERIFIABLE:pruned_history       the node pruned the block (real: WYRIWE's May block on the public node).
  UNVERIFIABLE:rpc_unreachable      RPC down / blocked / malformed response.
  UNVERIFIABLE:source_unavailable   git host / commit host unreachable.

Usage: python3 provenance_gate.py provenance-anchor-v0.vectors.json
Exit 0 iff every case reproduces its expected verdict, else 1.
"""
from __future__ import annotations
import json, os, re, sys

TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WITNESS_KINDS = {"onchain_commitment", "transparency_log", "forge_event"}

# content-unavailability status -> UNVERIFIABLE reason
CONTENT_UNAVAILABLE = {"unavailable_pruned": "pruned_history",
                       "unavailable_rpc": "rpc_unreachable",
                       "unavailable_source": "source_unavailable"}


def well_formed(anchor):
    """Return None if well-formed, else a malformed-reason string. Anchors carry NO self-reported time:
    precedence comes from the independent witness, never from a field the author controls."""
    if not isinstance(anchor, dict):
        return "not_an_object"
    kind = anchor.get("kind")
    if kind == "onchain_tx":
        if not isinstance(anchor.get("chain_id"), int):
            return "chain_id"
        if not (isinstance(anchor.get("tx"), str) and TX_RE.match(anchor["tx"])):
            return "tx"
        return None
    if kind == "onchain_deploy":
        if not isinstance(anchor.get("chain_id"), int):
            return "chain_id"
        if not (isinstance(anchor.get("address"), str) and ADDR_RE.match(anchor["address"])):
            return "address"
        return None
    if kind == "git_commit":
        if not (isinstance(anchor.get("repo"), str) and REPO_RE.match(anchor["repo"])):
            return "repo"
        if not (isinstance(anchor.get("commit"), str) and SHA_RE.match(anchor["commit"])):
            return "commit"
        w = anchor.get("witness")  # optional; a bare commit is well-formed but will be UNVERIFIABLE
        if w is not None:
            if not isinstance(w, dict) or w.get("kind") not in WITNESS_KINDS:
                return "witness_kind"
            if w["kind"] == "onchain_commitment" and not (
                    isinstance(w.get("chain_id"), int) and isinstance(w.get("tx"), str) and TX_RE.match(w["tx"])):
                return "witness_locator"
        return None
    return "kind"


def verdict(record, resolution):
    """Pure three-state verdict over a declared record + a modelled resolution (content/witness facts)."""
    thread = record.get("thread_opened_ts")
    if not isinstance(thread, int):
        return "FAIL:malformed_record"
    anchor = record.get("anchor")
    if anchor is None:
        return "FAIL:missing_anchor"
    if well_formed(anchor) is not None:
        return "FAIL:malformed_anchor"
    if resolution is None:
        return "UNVERIFIABLE:no_publication_witness"  # no evidence at all => fail-closed

    # Fact 1 — content identity.
    content = resolution.get("content")
    if content == "not_found":
        return "FAIL:anchor_not_found"
    if content in CONTENT_UNAVAILABLE:
        return f"UNVERIFIABLE:{CONTENT_UNAVAILABLE[content]}"
    if content != "confirmed":
        return "UNVERIFIABLE:rpc_unreachable"  # unknown status => never green

    # Fact 2 — existence witness (independent of the object's self-reported time).
    if not resolution.get("witness_declared"):
        return "UNVERIFIABLE:no_publication_witness"
    wts = resolution.get("witnessed_ts")
    if not isinstance(wts, int):
        return "UNVERIFIABLE:witness_unresolved"

    # Fact 3 — precedence, against the WITNESSED time.
    if wts >= thread:
        return "FAIL:postdates_thread"
    return "PASS"


def run(path):
    fx = json.load(open(path, encoding="utf-8"))
    cases = fx["cases"]
    fails = 0
    for c in cases:
        got = verdict(c["record"], c.get("resolution"))
        exp = c["expected"]
        ok = got == exp
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {c['name']:<34} -> {got:<36} (want {exp})")
    print(f"{len(cases) - fails}/{len(cases)} cases reproduced")
    return fails == 0


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "provenance-anchor-v0.vectors.json")
    sys.exit(0 if run(arg) else 1)
