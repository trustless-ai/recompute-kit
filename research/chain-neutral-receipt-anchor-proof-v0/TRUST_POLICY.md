# Independently selected verifier policy

Policy body ID `chain-neutral.verifier-policy.v0` binds subject_profile, proof_profile, log_id, exact checkpoint_id, anchor_mechanism, require_chain, require_timestamp and selected checkpoint_keys. `profile` identifies the policy schema. Its SHA256 of existing canonical body bytes is selected by the caller and referenced by the envelope.

`log_id` is a nonempty string, in both the policy and envelope. A correctly authenticated policy with a numeric log identity is not conformant. Explicit witnesses separately protect caller policy-digest selection, the envelope's policy reference, and the policy's proof-profile selection; their physical mutations preserve the positive controls and must be refuted by the corresponding witness.

The policy carries authority_id and an Ed25519 signature over UTF8(`chain-neutral.verifier-policy.v0\0`) || canonical(body). The caller supplies `{policy_id, authorities}` separately; `authorities` maps an already accepted ID to its SPKI public key. This authenticated signature and exact selection are checked before using checkpoint keys. A valid signature under an unknown authority does not pass. A proof cannot substitute a different profile/log/checkpoint or bootstrap trust using its own key.

The fixture caller context is independently selected **within the laboratory test**, not obtained from the proof. Its deterministic keys are publicly known; they establish no real-world identity, public-log authority, organizational independence, Bitcoin consensus, payment authority or trustworthy judgment. A deployment must supply independently authenticated policy authorities. This draft has no deployment provisioning mechanism and does not claim one.

Accepted policy profile, anchor-mechanism membership, envelope/policy mechanism equality and strict boolean `require_timestamp` are separately witnessed. Envelope keys stay untrusted even if they verify a checkpoint signature. For slot proofs, both the claimed inclusion root and the bridge's returned `log_root` must bind to the selected checkpoint. See [Echo review repairs](ECHO_REVIEW_REPAIRS.md) for the distinct removal controls and their limits.

The policy is an application trust input, not a new RVR Verification Profile. The native RVR SHA256_EQUALS example does not consume it. If a future RVR anchor-verification profile depends on policy, the policy, selected authority and all outcome-affecting inputs must enter that profile's existing committed closure. No ambient authority is introduced into RVR.
