#!/usr/bin/env python3
"""8263/precedence must put each OTS outcome in the right class.

The recipe shells out to the OpenTimestamps client. A digest that the proof does not commit to is a
definitive negative (the proof was read, and it is for something else), so it must be VERIFIED-BAD,
exit 1. Before this test the recipe reported it as UNVERIFIABLE ("not yet anchored"), exit 2: never a
pass, but in the wrong class, which hides a forgery behind "couldn't check".

The client is replaced by a fake on PATH so the test needs no network and no real proof:
  mismatch  -> the client's own mismatch message      -> must be exit 1, VERIFIED-BAD
  pending   -> no Bitcoin attestation yet             -> must stay exit 2, UNVERIFIABLE
The pending case proves the fix did not turn every non-anchored proof into a refutation.
"""
import os, stat, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEP = ROOT / "bin" / "recompute-step"
DIGEST = "d06ff4ce3f2704ad27e86cef489820b78a4bcacbed4f88c22f4256e428abcc3e"

OUTPUTS = {
    "mismatch": "Digest provided does not match digest in timestamp, "
                "d06ff4ce3f2704ad27e86cef489820b78a4bcacbed4f88c22f4256e428abcc3d (sha256)",
    "pending": "Calendar https://alice.btc.calendar.opentimestamps.org: Pending confirmation in Bitcoin blockchain",
}
EXPECT = {"mismatch": (1, "VERIFIED-BAD"), "pending": (2, "UNVERIFIABLE")}


def run(case: str):
    with tempfile.TemporaryDirectory() as d:
        fake = Path(d) / "ots"
        fake.write_text("#!/bin/sh\necho '%s' >&2\nexit 1\n" % OUTPUTS[case])
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        proof = Path(d) / "p.ots"
        proof.write_bytes(b"\x00")
        env = {**os.environ, "PATH": d + os.pathsep + os.environ.get("PATH", "")}
        r = subprocess.run([str(STEP), "8263/precedence", DIGEST, str(proof)],
                           capture_output=True, text=True, env=env, timeout=60)
        return r.returncode, r.stdout + r.stderr


def main() -> int:
    bad = 0
    for case, (code, label) in EXPECT.items():
        got, out = run(case)
        ok = got == code and label in out
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {case}: exit {got} (want {code}), {label!r} {'present' if label in out else 'MISSING'}")
        if not ok:
            print("   " + out.strip().replace("\n", "\n   ")[-400:])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
