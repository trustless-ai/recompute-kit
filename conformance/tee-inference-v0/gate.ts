// tee-inference.v0 CANDIDATE adapter — independent recompute of a 0G TeeML signed-inference
// attestation, per evidence class, WITHOUT collapsing the checks. For each vector the adapter
// re-derives the verdict from the vector's PUBLIC inputs only (no network, no SDK trust):
//
//   signature_recovery     recoverAddress(hashMessage(preimage), signature) == claimed_signer   [recomputed]
//   anti_replay_binding    is chatID / zg_res_key bound inside the signed preimage?              [recomputed]
//   response_digest_binding sha256(response_canonical_string) == attested_response_hash          [recomputed]
//   enclave_quote_parse    is a local-TEE attestation report actually available to parse?        [attested]
//
// The suite's `expected` is the value pulled from the PRIMARY ARTIFACT (a real captured
// TeeML inference — gist TMerlini/19d532bc… teeml-sample.json), so conformance = "an independent
// recompute reproduces the same per-check verdict + derived value." --tamper models a broken
// implementation that reports 3b as verified (green) despite no quote — caught by the vector.
// Adapter contract for bin/conformance-suite: fixture JSON on stdin -> {name: {…verdict}} on stdout.
import { ethers } from "ethers";
import { createHash } from "node:crypto";

const sha256 = (s: string) => createHash("sha256").update(s, "utf8").digest("hex");
const RECOMPUTED = "recomputed", ATTESTED = "attested";

function verdictFor(v: any, tamper: boolean): Record<string, unknown> {
  const i = v.inputs;
  switch (v.check) {
    case "signature_recovery": {
      let recovered: string;
      try { recovered = ethers.verifyMessage(i.preimage, i.signature); } catch { recovered = "0xINVALID"; }
      const ok = recovered.toLowerCase() === String(i.claimed_signer).toLowerCase();
      return { status: ok ? "verified" : "rejected", evidence_basis: RECOMPUTED, recovered };
    }
    case "anti_replay_binding": {
      const bound = String(i.preimage).includes(String(i.chatID));
      return { status: bound ? "verified" : "unverifiable", evidence_basis: RECOMPUTED, chatid_in_preimage: bound };
    }
    case "response_digest_binding": {
      const ok = sha256(String(i.response_canonical_string)) === i.attested_response_hash;
      return { status: ok ? "verified" : "rejected", evidence_basis: RECOMPUTED, recomputed_hash: sha256(String(i.response_canonical_string)) };
    }
    case "enclave_quote_parse": {
      // A quote is parseable only if the provider actually serves a local-TEE attestation report.
      const report = String(i.attestation_report_response);
      const available = !/not available|without local TEE|forwards to an upstream|"error"/i.test(report);
      // --tamper: a non-conformant impl that greenlights the enclave check with no quote in hand.
      if (tamper) return { status: "verified", evidence_basis: ATTESTED, attestation_available: true };
      return { status: available ? "verified" : "unverifiable", evidence_basis: ATTESTED, attestation_available: available };
    }
    default:
      return { status: "unverifiable", evidence_basis: RECOMPUTED };
  }
}

if (import.meta.main) {
  const tamper = Bun.argv.includes("--tamper");
  if (Bun.argv.includes("--grade")) {
    const fx = JSON.parse(await Bun.stdin.text());
    const out: Record<string, unknown> = {};
    for (const v of fx.vectors) out[v.name] = verdictFor(v, tamper);
    console.log(JSON.stringify(out));
    process.exit(0);
  }
  const fx = JSON.parse(await Bun.file(`${import.meta.dir}/tee-inference-v0.vectors.json`).text());
  for (const v of fx.vectors) {
    const got = JSON.stringify(verdictFor(v, false));
    const exp = JSON.stringify(v.expected);
    console.log(`${got === exp ? "✓" : "✗"} ${v.name}`);
  }
}
