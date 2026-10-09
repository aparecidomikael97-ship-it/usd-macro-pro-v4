# AION V2 — Four-role Ed25519 key enrollment + rotation/revocation (reference only)

**09 October 2026.** Parent Draft #1130 → #1129 → #1128 → #1127 → #1126 → #1125. **NO-GO** on any actual enrollment, payments, cloud deployment, PC installation, signing with real owner keys or merge.

## Why this is the next hard gate

The signed primary-witness and secondary-anchor protocol (#1127–#1130) accepts caller-injected public pins as mathematical inputs, not the genuine enrolled keys of a trusted owner, witness or collector. An attacker who changes *both* a signer and its expected public key can pass signature verification. Four valid mathematical signatures do not prove four independently operated administrative domains, nor genuine owner presence.

This reference adds an **exact, versioned, domain-separated roster** with four roles:
- `HUMAN_OWNER`: true owner identity and consent key; fixture only here
- `COLLECTOR`: append receipt signing key; must not be reused as owner
- `PRIMARY_WITNESS`: signed head READ; separate administration
- `SECONDARY_ANCHOR`: separately signed high-watermark; separate administration

Every role has one unique exact `key_id` and Ed25519 `public_key_hex`; all four must have unique public key bytes, claimed domain IDs and key IDs. Each signer provides a **role-bound proof-of-possession (POP)** signature over the **full canonical roster**, with challenge, policy generation, scope, previous hash, all public pins, domain assertions and sorted revoked key fingerprints. The owner additionally signs the whole roster under a **different owner-approval domain**.

### Genesis and later rotation

- The first roster requires generation 1, `previous_roster_sha256=0...`, empty revocations and a caller-supplied owner pin matching the proposed owner pin.
- A later generation must increment exactly by one and bind exact `roster_sha256` of the previous roster. New public keys must prove possession. The **previous owner signing key** must approve the **new** roster even when the owner key changes; a newly generated owner key cannot approve its own transition.
- All replaced old public keys must appear in the sorted revocation fingerprint set. Prior revocations must be preserved (no silent un-revocation); none of the active keys can appear in the revoked set. Key-ID-only renaming without changing key bytes is rejected. No-op generation advance is rejected.
- The previous roster, generation, owner trust pin and accepted challenge are *caller supplied* references. This module does not know whether a prior roster was authorized, how it was stored, or whether a client nonce was unpredictable, unique, consumed or rolled back.
- Domain claims (e.g. Cloudflare and AWS admin principal IDs) are **assertions**, not account/IAM/hardware attestations. Changing all claimed domain IDs and roots together can still pass mathematical checks.

### Deliberate attack counterexample

Disposable CI creates synthetic attacker keys for all four roles, substitutes the expected `HUMAN_OWNER` root pin with the attacker's matching pin and signs its own initial roster. The result is `FOUR_ROLE_ROSTER_MATH_VALID_UNTRUSTED`. The fake proves that the first trust root and all subsequent keys **must be enrolled through a real, independently witnessed owner-presence ceremony** rather than accepting a bootstrapped signature by itself.

### What remains required before trust can be promoted

1. Genuine Windows Hello / FIDO2 owner presence on an explicitly authorized physical device, with hardware-backed challenge when supported, root key lifecycle and recovery. No private key in GitHub code, secrets, CI, logs or ChatGPT.
2. Signed, trust-anchored immutable generation head (in an independently protected trust domain, *not* restorable with Cloudflare PITR or both provider admins), antirollback checks on each read and write, protected nonce/challenge consumption.
3. Proof of separate operator credential/IAM control and independent public-key custody for collector, primary witness and secondary anchor. Role/public pin assertions are insufficient.
4. Revocation/rotation transaction acknowledged and enforced by both witness domains **before** future paid dispatch; secure recovery after lost response, conflicting rotations, revoked root, offline witnesses and unknown payment outcome.
5. Protected budget authorization and exact paid request dispatch receipt including external unknown outcomes. The current local SQLite V2 budget/reference and two-domain CAS prototypes are not globally atomic.
6. Quote and control total monthly R$200 budget for **all** existing and new infrastructure; obtain explicit owner authorization for any resource or spending.

### Reference-only code

`atlasquant_aion_v2_four_role_key_enrollment_reference.py` exports `review_four_role_roster`, `canonical_roster_bytes`, `owner_approval_transcript`, `role_pop_transcript`, `roster_sha256`. No real key creation or signing, no I/O, network or registry writes. Tests generate disposable Ed25519 keys, mutate signatures/scopes/keys, simulate valid reference transitions, enforce revocation rules, deliberately forge genesis and validate previous owner approval.

The test matrix on Windows and Ubuntu reruns #1130 two-domain signing, #1129 durable simulated CAS, #1128 signed READ, #1127 rollback, #1126 nonce budget, #1125 V2 full request, and inherited V1/provider protections.

**All authority fields remain false:** owner presence, key custody, trusted owner consent, independent administration, protected registry, external generation anchor, nonce replay protection, real spending, model invocation, provider called, installer and safe-to-resume. Never feed `FOUR_ROLE_ROSTER_MATH_VALID_UNTRUSTED` into any `request_approved=True` path.

**No real keys, no cloud provisioning, no merge, no deploy, no paid call, no Windows/TPM or local host access.**
