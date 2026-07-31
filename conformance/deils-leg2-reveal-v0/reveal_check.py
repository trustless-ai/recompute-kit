#!/usr/bin/env python3
"""Independent DEILS leg-2 reveal-binding checker (ours). Derives every verdict from the rule itself —
commitment_hash = "sha256:" + sha256(JCS(parsed(content))); the input to JCS is ALWAYS the parsed
(language-native) value, NEVER the served wire encoding (Pavlo/Fede, 2026-07-31, closing the byte-domain
ambiguity Merlini's \\uXXXX-escaping catch surfaced). A reveal binds iff the recompute matches; a null
reveal is content_withheld; an unequal recompute is content_commitment_mismatch (terminal, fail-closed).

Two-sided on the wire-trap: for a case carrying `wire_representation_ascii_escaped`, we ALSO assert that
byte-hashing the served (\\uXXXX-escaped) wire string does NOT match the commitment — a conforming checker
must re-parse+re-canonicalize, never hash the wire bytes as-received.

Does NOT read invinoveritas's check_deils_leg2.py — the point is a BLIND diff of two implementations.
"""
import json, hashlib, sys

def jcs(v):  # RFC 8785 JCS: recursive sorted keys, compact, raw UTF-8 (ensure_ascii=False)
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def commit(parsed_content):
    return "sha256:" + hashlib.sha256(jcs(parsed_content).encode("utf-8")).hexdigest()

def check(case):
    # Two ways to name the commitment: recompute it from committed_content (synthetic vectors), OR pin
    # it to the STORED commitment_hash string a real record actually published (blind-hit against a live
    # record — e.g. Fede's content_withheld/reveal cycle). When a stored hash is given we do NOT trust it;
    # we still recompute from the revealed content below and check the recompute equals what was stored.
    committed_hash = case.get("stored_commitment_hash") or commit(case["committed_content"])  # rule: jcs(parsed(content))
    rc = case.get("revealed_content", None)
    state = "content_withheld" if rc is None else (
        "content_bound" if commit(rc) == committed_hash else "content_commitment_mismatch")
    ok = state == case["expected_state"]
    notes = []
    # two-sided wire trap: hashing the served escaped bytes must NOT equal the commitment
    if "wire_representation_ascii_escaped" in case:
        wire = case["wire_representation_ascii_escaped"]
        wire_byte_hash = "sha256:" + hashlib.sha256(wire.encode("utf-8")).hexdigest()
        wire_mismatches = wire_byte_hash != committed_hash
        want = case.get("wire_byte_hash_must_not_match_commitment", True)
        ok = ok and (wire_mismatches == want)
        notes.append(f"wire-byte-hash≠commitment={wire_mismatches} (want {want})")
    return ok, state, notes

fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "vectors.json"))
fails = 0
for c in fx["cases"]:
    ok, state, notes = check(c)
    fails += not ok
    extra = ("  · " + " · ".join(notes)) if notes else ""
    print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<32} → {state}{extra}")
print(f"\n{len(fx['cases'])-fails}/{len(fx['cases'])} cases reproduced blind" + ("" if not fails else "  ← MISMATCH"))
sys.exit(1 if fails else 0)
