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

Plus two filename cases (pipavlo82, PR #90 review): the client echoes the proof's filename in other
errors, so a proof named "...does not match digest in timestamp.ots" must not read as a mismatch.
The proof is never read in either, so both must stay exit 2, UNVERIFIABLE:
  missing file   -> argparse "can't open '<name>'" (client exits 2)
  invalid file   -> "Invalid timestamp file '<name>'" (client exits 1)
  not a proof    -> "Error! '<name>' is not a timestamp file." (client exits 1)
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

TRAP = "does not match digest in timestamp.ots"   # a proof filename that contains the diagnostic
# (name, client stderr, client exit code, proof filename, proof exists, want rc, want marker)
# "{proof}" in the stderr is replaced with the proof's full path, as the real client echoes it.
CASES = [
    ("mismatch",
     "Digest provided does not match digest in timestamp, "
     "a42205d7e39c684f0aa43f80fe7ea1aa8e180df93ff46e82b5bff95b70c663e9 (sha256)",
     1, "p.ots", True, 1, "VERIFIED-BAD"),
    ("pending", "Pending confirmation in Bitcoin blockchain", 1, "p.ots", True, 2, "UNVERIFIABLE"),
    ("no-output", "", 1, "p.ots", True, 2, "UNVERIFIABLE"),
    ("filename-missing",
     "usage: ots verify [-h] [-f TARGET | -d DIGEST] TIMESTAMP\n"
     "ots verify: error: argument TIMESTAMP: can't open '{proof}': "
     "[Errno 2] No such file or directory: '{proof}'",
     2, TRAP, False, 2, "UNVERIFIABLE"),
    ("filename-invalid",
     "Invalid timestamp file '{proof}': Expected magic bytes",
     1, TRAP, True, 2, "UNVERIFIABLE"),
    ("filename-not-a-proof",
     "Error! '{proof}' is not a timestamp file.",
     1, TRAP, True, 2, "UNVERIFIABLE"),
]


def run(stub_stderr: str, stub_rc: int, proof_name: str, proof_exists: bool) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as d:
        proof = Path(d) / proof_name
        if proof_exists:
            proof.write_bytes(b"\x00")
        msg = Path(d) / "stderr.txt"
        msg.write_text(stub_stderr.replace("{proof}", str(proof)) + "\n" if stub_stderr else "")
        stub = Path(d) / "ots"
        stub.write_text(f"#!/bin/sh\ncat '{msg}' >&2\nexit {stub_rc}\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{d}:{os.environ.get('PATH', '')}")
        return subprocess.run(["bash", str(STEP), "8263/precedence", DIGEST, str(proof)],
                              capture_output=True, text=True, env=env, timeout=60)


def main() -> int:
    failed = 0
    for name, stderr, stub_rc, proof_name, exists, want_rc, want_marker in CASES:
        r = run(stderr, stub_rc, proof_name, exists)
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
