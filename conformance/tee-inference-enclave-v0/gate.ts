// tee-inference-enclave.v0 CANDIDATE adapter — the fully-recomputed genuine-enclave case. Every check is
// re-derived from the vector's PUBLIC bytes, with NO reliance on 0G's `tee_verified` router flag:
//
//   signature_recovery  recoverAddress(hashMessage(preimage), signature) == claimed_signer   (EIP-191)
//   request_digest      sha256(canonical) == the signed H(request)      (client-recomputable — genuine enclave)
//   response_digest     sha256(canonical) == the signed H(response)
//   rtmr_replay         SHA-384-extend the RTMR event log == the quote's RTMR0-3
//   equality            report_data == recovered signer · registry teeSignerAddress == report_data
//
// The suite's `expected` is the value pulled from the PRIMARY ARTIFACT (a real mainnet glm-5.2 inference:
// provider 0x7DCFe6…, signer 0xA46EA4…). --tamper models a broken impl. Adapter contract for
// bin/conformance-suite: fixture JSON on stdin -> {name: {…verdict}} on stdout.
import { ethers } from "ethers";
import { createHash } from "node:crypto";

const sha256 = (s: string) => createHash("sha256").update(s, "utf8").digest("hex");
const sha384 = (b: Buffer) => createHash("sha384").update(b).digest();

function rtmrReplay(log: { imr: number | string; digest: string }[], quoteRtmrs: string[]): boolean[] {
  return [0, 1, 2, 3].map((imr) => {
    let acc = Buffer.alloc(48);
    for (const e of log) if (Number(e.imr) === imr && e.digest) acc = sha384(Buffer.concat([acc, Buffer.from(e.digest, "hex")]));
    return acc.toString("hex") === quoteRtmrs[imr];
  });
}

function verdict(v: any): Record<string, unknown> {
  const i = v.inputs;
  switch (v.check) {
    case "signature_recovery": {
      let recovered = "0xINVALID";
      try { recovered = ethers.verifyMessage(i.preimage, i.signature); } catch {}
      const ok = recovered.toLowerCase() === String(i.claimed_signer).toLowerCase();
      return { status: ok ? "verified" : "rejected", evidence_basis: "recomputed", recovered };
    }
    case "request_digest":
    case "response_digest": {
      const h = sha256(String(i.canonical));
      return { status: h === i.attested_hash ? "verified" : "rejected", evidence_basis: "recomputed", recomputed_hash: h };
    }
    case "rtmr_replay": {
      const matched = rtmrReplay(i.event_log, i.quote_rtmrs);
      return { status: matched.every(Boolean) ? "verified" : "rejected", evidence_basis: "recomputed", matched };
    }
    case "equality":
      return { status: String(i.a).toLowerCase() === String(i.b).toLowerCase() ? "verified" : "rejected", evidence_basis: "recomputed" };
    default:
      return { status: "unverifiable", evidence_basis: "recomputed" };
  }
}

if (import.meta.main) {
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors) out[v.name] = verdict(v);
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/tee-inference-enclave-v0.vectors.json`).text());
  for (const v of fx.vectors) {
    const got = JSON.stringify(verdict(v)), exp = JSON.stringify(v.expected);
    console.log(`${got === exp ? "✓" : "✗"} ${v.name}`);
  }
}
