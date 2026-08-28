#!/usr/bin/env python3
"""provenance-anchor.v0 — build-first origination gate (verdict logic).

SCOPE — deterministic verdict logic. Resolution is a MODEL INPUT (companion resolve_anchor.py produces the
real one); the graded suite stays byte-deterministic. It proves a WITNESSED temporal + existence claim and
nothing about semantics.

FOUR facts, each independently established (extends @pipavlo82's three-fact contract — both SIDES of the
comparison must be witnessed, and the witness must be BOUND to the thing it witnesses):
  1. content identity   — the object exists and its bytes/hash are stable.
  2. existence witness   — an INDEPENDENT observation of when the object was public; NOT its self-reported
                           time. On-chain tx: intrinsic (consensus block). Git commit: a SEPARATE witness.
  3. subject binding     — the witness must reference THIS subject. An on-chain commitment of a commit must
                           actually carry that commit hash in its calldata; a block timestamp from an
                           unrelated tx is not a witness of the commit.
  4. witnessed precedence — the witnessed anchor time strictly precedes the witnessed THREAD-OPEN time.
                           thread-open is itself a witnessed fact (e.g. the ERC PR's forge-stamped
                           creation), never an unverified record field a caller can move.

The gate does not trust the resolution blindly: it checks the resolution is COHERENT with the declared
anchor (a bare commit cannot claim a witness), fails closed on a non-object resolution, and rejects bool
where an int is required. If any fact is unmet the verdict is UNVERIFIABLE or FAIL, never a silent PASS.

Verdict (closed enumeration, never a silent green):
  PASS
  FAIL:missing_anchor | malformed_anchor | missing_thread_open | malformed_thread_open
      | anchor_not_found | postdates_thread
  UNVERIFIABLE:no_publication_witness | witness_unresolved | witness_not_bound | incoherent_resolution
      | thread_unwitnessed | pruned_history | rpc_unreachable | source_unavailable

Usage: python3 provenance_gate.py provenance-anchor-v0.vectors.json
Exit 0 iff every case reproduces its expected verdict, else 1.
"""
from __future__ import annotations
import json, os, re, sys

TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ANCHOR_WITNESS_KINDS = {"onchain_commitment", "transparency_log", "forge_event"}
THREAD_WITNESS_KINDS = {"onchain_commitment", "forge_event"}
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

    # Witnessed precedence — both sides are now independently witnessed.
    if awts >= twts:
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
        print(f"{'OK ' if ok else 'BAD'} {c['name']:<34} -> {got:<38} (want {exp})")
    print(f"{len(cases) - fails}/{len(cases)} cases reproduced")
    return fails == 0


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "provenance-anchor-v0.vectors.json")
    sys.exit(0 if run(arg) else 1)
