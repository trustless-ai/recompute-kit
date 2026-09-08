#!/usr/bin/env python3
"""profile-amendment.v0 — recompute whether a verification-profile change is an AUTHORIZED
transition or an unauthorized swap.

Sibling to companion-envelope-v0. Same discipline: a change that cannot be shown authorized is
UNRESOLVED, never silently permitted, and the effective profile FAILS CLOSED to the prior one.

  prior_profile_commitment = sha256(JCS(in_force_profile))
  new_profile_commitment   = sha256(JCS(proposed_profile))
  amendment (preimage)     = {schema, prior_profile_commitment, new_profile_commitment, escrow_ref}
  amendment_cc             = sha256(JCS(amendment))
  authorization (party)    = {party, signed_digest, pubkey}         (signed_digest MUST == amendment_cc)

A change from profile A to profile B is a PERMITTED transition only if, together:
  (1) an amendment object exists whose declared commitments equal the recomputed prior/new profile
      commitments AND whose escrow_ref equals this task's escrow_ref  (it binds THIS A->B for THIS task), and
  (2) every required party has an authorization whose signed_digest is present AND == amendment_cc
      (both sides co-signed THIS exact amendment, not some other one).
Otherwise transition_status is "unresolved" and effective_profile_commitment stays the prior commitment:
a bare hash change, a one-sided signature, a wrong-prior chain, a replayed escrow_ref, or an authorization
naming a different amendment all fail closed. Legitimacy is evidenced by the transition artifact, never
inferred from the fact that the profile hash is different (a legitimate amendment and an unauthorized swap
are indistinguishable at the hash level unless the transition itself is bound and co-signed — @Pavlentyy82,
@babyblueviper1, WG 2026-09-08). The two-party co-signature is the one delta from the single-owner
pq-key-binding rotation edge; the resolution shape (in force at the artifact's anchor time) is the same.

This gate checks the BINDING, not signature cryptography: an authorization is bound iff its signed_digest
equals amendment_cc, exactly as companion-envelope checks content_address == verdict_core_cc. ML-DSA / ECDSA
validity of each signature rides the separate signature lane, unchanged.
"""
import sys, json, hashlib, os

def jcs(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()

def profile_cc(profile):
    return sha(jcs(profile))

def profile_transition(v):
    in_force = v["in_force_profile"]
    proposed = v["proposed_profile"]
    escrow_ref = v["escrow_ref"]
    amendment = v.get("amendment")
    authorizations = v.get("authorizations") or {}
    required = v.get("required_parties") or ["buyer", "supplier"]

    prior_cc = profile_cc(in_force)
    new_cc = profile_cc(proposed)

    amendment_cc = None
    amend_binds = False
    if amendment:
        # amendment_cc is recomputed from the amendment's OWN declared fields, so an authorization
        # is checked against exactly what its signer saw — not against what we wish it had signed.
        preimage = {
            "schema": "profile-amendment.v0",
            "prior_profile_commitment": amendment.get("prior_profile_commitment"),
            "new_profile_commitment": amendment.get("new_profile_commitment"),
            "escrow_ref": amendment.get("escrow_ref"),
        }
        amendment_cc = sha(jcs(preimage))
        # (1) does the amendment bind THIS transition: its declared commitments == the recomputed
        # profile commitments, and its escrow_ref == this task's escrow_ref.
        amend_binds = (amendment.get("prior_profile_commitment") == prior_cc
                       and amendment.get("new_profile_commitment") == new_cc
                       and amendment.get("escrow_ref") == escrow_ref)

    # (2) every required party co-signed THIS amendment: signed_digest present AND == amendment_cc.
    def bound(party):
        a = authorizations.get(party)
        return bool(a and a.get("signed_digest") and amendment_cc is not None
                    and a["signed_digest"] == amendment_cc)
    all_authorized = amendment_cc is not None and all(bound(p) for p in required)

    permitted = bool(amend_binds and all_authorized)
    status = "permitted" if permitted else "unresolved"
    # fail closed: an unauthorized change never takes effect; the in-force profile is unchanged.
    effective_cc = new_cc if permitted else prior_cc
    return {
        "prior_profile_commitment": prior_cc,
        "new_profile_commitment": new_cc,
        "amendment_cc": amendment_cc,
        "transition_status": status,
        "effective_profile_commitment": effective_cc,
    }

KEYS = ("prior_profile_commitment", "new_profile_commitment", "amendment_cc",
        "transition_status", "effective_profile_commitment")

def run(path):
    doc = json.load(open(path))
    fails = 0
    for v in doc["vectors"]:
        got, exp = profile_transition(v), v["expect"]
        ok = all(got[k] == exp[k] for k in KEYS)
        fails += not ok
        print(f"{'OK ' if ok else 'BAD'} {v['name']:<34} status={got['transition_status']:<10} "
              f"amendment_cc={str(got['amendment_cc'])[:12]}")
    print(f"{len(doc['vectors']) - fails}/{len(doc['vectors'])} vectors reproduced")
    return fails

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    sys.exit(1 if run(arg or os.path.join(here, "profile-amendment-v0.vectors.json")) else 0)
