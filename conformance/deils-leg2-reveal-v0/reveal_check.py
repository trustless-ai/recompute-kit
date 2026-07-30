#!/usr/bin/env python3
"""Independent DEILS leg-2 reveal-binding checker (ours). Derives every verdict from the rule itself —
commitment_hash = "sha256:" + sha256(JCS(committed_content)); reveal recomputes over revealed_content and
binds iff equal; null reveal = content_withheld. Does NOT read Fede's check_deils_leg2.py — the point is a
BLIND diff of two independent implementations over the same vectors."""
import json, hashlib, sys

def jcs(v):  # RFC 8785 JCS: recursive sorted keys, compact, raw UTF-8
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def commit(content):
    return "sha256:" + hashlib.sha256(jcs(content).encode("utf-8")).hexdigest()

def verdict(case):
    committed_hash = commit(case["committed_content"])
    rc = case.get("revealed_content", None)
    if rc is None:
        return "content_withheld", committed_hash, None
    recomputed = commit(rc)
    return ("content_bound" if recomputed == committed_hash else "content_commitment_mismatch"), committed_hash, recomputed

fx = json.load(open(sys.argv[1]))
fails = 0
for c in fx["cases"]:
    got, ch, rh = verdict(c)
    exp = c["expected_state"]
    ok = got == exp
    fails += not ok
    print(f"{'OK ' if ok else 'BAD'} {c['case_id']:<26} → {got:<28} (expected {exp})")
print(f"\n{len(fx['cases'])-fails}/{len(fx['cases'])} cases reproduced blind" + ("" if not fails else "  ← MISMATCH"))
sys.exit(1 if fails else 0)
