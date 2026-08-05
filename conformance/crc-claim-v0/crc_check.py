#!/usr/bin/env python3
"""crc-claim-v0 conformance — gates the crc/* recipes through the PUBLIC interface
(bin/recompute-step subprocess), never against their own internals.

Covers:
  · golden vector: #236 ClaimPreimage → sha256:df1a6bfe… (exit 0)
  · a negative vector at EVERY pre-hash-gate predicate (exit 1, one per rule —
    a rule without a failing vector is a rule nobody has watched fire)
  · lift.v0 byte-compatibility: /ledger #236 fixture → the SAME claim_id (exit 0)
  · cell envelopes: node-1 nostr + node-2 eip712 real #236 v1 Cells verify (exit 0);
    tampered schnorr sig and wrong registered key reject (exit 1);
    eip712 lane counts SKIPPED (not passed) when eth-account is missing (exit 2)

Derivation source: trustless-ai/cross-reference-console@a82f8f1 (CLAIM.md gate,
CELL-v1.md envelopes) — the vectors come from the frozen spec + the live edge,
never from this kit's implementation.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "..", "..", "bin", "recompute-step")
FIX = os.path.join(HERE, "fixtures")
GOLDEN_ID = "sha256:df1a6bfe3063186f8a8327b75a5bfddae12d3518f2cc16f8fddbc6c311de9512"
NODE1_PUBKEY = "6786e18a864893a900bd9858e650f67ccc3513f248fed374b591e2ff6922fbb7"
NODE2_ADDR = "0x85Fa13511D170FBe173761b63D7f8DD4A6f6Bf1A"

passed, failed, skipped = [], [], []


def run(args, stdin_text=None):
    return subprocess.run([STEP] + args, input=stdin_text, capture_output=True, text=True).returncode


def expect(label, args, want, stdin_text=None):
    got = run(args, stdin_text)
    if got == want:
        print(f"  ok · {label}"); passed.append(label)
    elif want == 0 and got == 2:
        print(f"  SKIP · {label} (UNVERIFIABLE — missing optional dep; not a pass)"); skipped.append(label)
    else:
        print(f"  FAIL · {label} (exit {got}, wanted {want})"); failed.append(label)


base = json.load(open(os.path.join(FIX, "golden-preimage.json")))


def mutated(**changes):
    d = dict(base); d.update(changes)
    return json.dumps(d)


print("crc/claim-id — golden + negative-per-predicate:")
expect("golden #236 preimage derives df1a6bfe…",
       ["crc/claim-id", os.path.join(FIX, "golden-preimage.json"), GOLDEN_ID], 0)
expect("duplicate member rejects", ["crc/claim-id", "-"], 1, '{"a":1,"a":2}')
expect("nested duplicate rejects", ["crc/claim-id", "-"], 1, '{"x":{"a":1,"a":2}}')
expect("missing field rejects", ["crc/claim-id", "-"], 1,
       json.dumps({k: v for k, v in base.items() if k != "as_of"}))
expect("extra field rejects", ["crc/claim-id", "-"], 1, mutated(extra="x"))
expect("schema mismatch rejects", ["crc/claim-id", "-"], 1, mutated(schema="crc.claim.v1"))
expect("empty string field rejects", ["crc/claim-id", "-"], 1, mutated(profile_id=""))
expect("claim_body wrong type rejects", ["crc/claim-id", "-"], 1, mutated(claim_body=7))
expect("claimant bool rejects", ["crc/claim-id", "-"], 1, mutated(claimant=True))
expect("claimant string rejects", ["crc/claim-id", "-"], 1, mutated(claimant="54848"))
expect("artifact_hash sha256: prefix rejects", ["crc/claim-id", "-"], 1,
       mutated(artifact_hash="sha256:" + base["artifact_hash"]))
expect("artifact_hash 0x prefix rejects", ["crc/claim-id", "-"], 1,
       mutated(artifact_hash="0x" + base["artifact_hash"]))
expect("artifact_hash uppercase rejects", ["crc/claim-id", "-"], 1,
       mutated(artifact_hash=base["artifact_hash"].upper()))
expect("artifact_hash short rejects", ["crc/claim-id", "-"], 1,
       mutated(artifact_hash=base["artifact_hash"][:-1]))
expect("claimant negative rejects", ["crc/claim-id", "-"], 1, mutated(claimant=-1))
expect("claimant > uint256 rejects", ["crc/claim-id", "-"], 1, mutated(claimant=2**256))
expect("as_of offset form rejects", ["crc/claim-id", "-"], 1, mutated(as_of="2026-08-04T00:11:24+00:00"))
expect("as_of fractional seconds rejects", ["crc/claim-id", "-"], 1, mutated(as_of="2026-08-04T00:11:24.000Z"))
expect("as_of impossible instant rejects", ["crc/claim-id", "-"], 1, mutated(as_of="2026-13-04T00:11:24Z"))
expect("tampered claim_body changes id (mismatch)",
       ["crc/claim-id", "-", GOLDEN_ID], 1, mutated(claim_body="accept"))

print("crc/lift-v0 — byte-compatibility with the hand-minted claim:")
expect("lifting /ledger #236 fixture derives the SAME claim_id",
       ["crc/lift-v0", os.path.join(FIX, "ledger-236-entry.json"), GOLDEN_ID], 0)

print("crc/cell-verify — both real #236 v1 Cells + tamper negatives:")
expect("node-1 nostr Cell verifies vs registered pubkey",
       ["crc/cell-verify", os.path.join(FIX, "node1-nostr.cell.json"), "nostr", NODE1_PUBKEY], 0)
n1 = json.load(open(os.path.join(FIX, "node1-nostr.cell.json")))
sig = bytearray.fromhex(n1["event"]["sig"]); sig[5] ^= 1
n1["event"]["sig"] = sig.hex()
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as t:
    json.dump(n1, t); tampered = t.name
expect("tampered schnorr sig rejects", ["crc/cell-verify", tampered, "nostr", NODE1_PUBKEY], 1)
os.unlink(tampered)
expect("wrong registered pubkey rejects",
       ["crc/cell-verify", os.path.join(FIX, "node1-nostr.cell.json"), "nostr", "ab" * 32], 1)
expect("node-2 eip712 Cell verifies (quadruple equality)",
       ["crc/cell-verify", os.path.join(FIX, "node2-eip712.cell.json"), "eip712", NODE2_ADDR], 0)
expect("wrong registered address rejects",
       ["crc/cell-verify", os.path.join(FIX, "node2-eip712.cell.json"), "eip712",
        "0x347aeeF3a6f8fD71C93289ab90c8dC0b26A8300a"], 1)

print(f"\n{len(passed)} passed · {len(failed)} failed · {len(skipped)} skipped(unverifiable)")
if failed:
    print("FAILED:", failed); sys.exit(1)
print("crc-claim-v0: CONFORMANT")
