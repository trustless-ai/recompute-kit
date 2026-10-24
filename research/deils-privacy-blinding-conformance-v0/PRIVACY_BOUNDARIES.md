# Privacy and authorization limits

Blinding raises the cost of candidate checking only under an actual entropy/secrecy assumption. A small unblinded GPS candidate space permits offline matching. The deterministic experiment uses 100 synthetic candidates and a public laboratory nonce; the attacker without that nonce is only tested against those 100 unblinded guesses. Disclosure of the nonce restores dictionary matching. This neither measures all possible attacks nor proves impossibility of recovery.

Commitment hiding is not private transport/reveal, authenticated encryption, recipient authorization, selective disclosure, or external execution evidence. Blinding does not enforce provider-only or wallet-owner-only access. No cipher, key lifecycle, authorization system or production client schema is implemented. Existence metadata can still leak timing/frequency. Freshness/secret handling must be enforced operationally by the actual issuer; cross-commitment reuse cannot be ruled out by one isolated verifier.

Selective disclosure would need a separate versioned Merkle profile and independent threat model. DEILS content commitment, ReceiptOS envelope root and agent-action subject identity remain distinct.
