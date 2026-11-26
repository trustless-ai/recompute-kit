#!/usr/bin/env python3
"""8263/precedence must classify a digest the .ots proof does not commit to as VERIFIED-BAD.

Before the fix the OTS client's "Digest provided does not match digest in timestamp" fell through
to the anchor regex and came back as UNVERIFIABLE (exit 2, "pending, or node unreachable"). It
never passed, but it answered "couldn't check" to a question that had been checked and answered
no. Found recomputing ERC-8299 ledger entry 38 with one nibble of the digest flipped.

Offline by construction: a stand-in `ots` on PATH prints what the real client prints, so neither
network nor the OpenTimestamps client is needed. Three cases, so the fix cannot pass by
reclassifying everything:
  mismatch  -> exit 1, VERIFIED-BAD     (the fix)
  pending   -> exit 2, UNVERIFIABLE     (genuinely couldn't check: must stay 2)
  no output -> exit 2, UNVERIFIABLE     (the regex miss path is untouched)
"""
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEP = ROOT / "bin" / "recompute-step"
DIGEST = "a42205d7e39c684f0aa43f80fe7ea1aa8e180df93ff46e82b5bff95b70c663e8"

CASES = [
    ("mismatch",
     "Digest provided does not match digest in timestamp, "
     "a42205d7e39c684f0aa43f80fe7ea1aa8e180df93ff46e82b5bff95b70c663e9 (sha256)",
     1, "VERIFIED-BAD"),
    ("pending", "Pending confirmation in Bitcoin blockchain", 2, "UNVERIFIABLE"),
    ("no-output", "", 2, "UNVERIFIABLE"),
]


def run(stub_stderr: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as d:
        stub = Path(d) / "ots"
        stub.write_text("#!/bin/sh\nprintf '%s\\n' " + repr(stub_stderr) + " >&2\nexit 1\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        proof = Path(d) / "p.ots"
        proof.write_bytes(b"\x00")
        env = dict(os.environ, PATH=f"{d}:{os.environ.get('PATH', '')}")
        return subprocess.run(["bash", str(STEP), "8263/precedence", DIGEST, str(proof)],
                              capture_output=True, text=True, env=env, timeout=60)


def main() -> int:
    failed = 0
    for name, stderr, want_rc, want_marker in CASES:
        r = run(stderr)
        out = r.stdout + r.stderr
        ok = r.returncode == want_rc and want_marker in out
        print(f"{'ok  ' if ok else 'FAIL'} {name}: rc={r.returncode} (want {want_rc}), "
              f"marker {want_marker!r} {'present' if want_marker in out else 'ABSENT'}")
        if not ok:
            print(out[-400:])
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
