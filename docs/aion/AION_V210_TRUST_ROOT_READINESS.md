# AION V2.10 — Provenance trust-root readiness preflight

## Purpose

V2.10 does **not** authenticate provenance. It defines the fail-closed preflight
that must remain BLOCKED until a real trust architecture exists.

The repository currently has no reusable signing/trust infrastructure for this
boundary. A repository-wide search did not find an existing signer/key-id model,
trust anchor, FIDO/WebAuthn attestation path, HMAC/Ed25519/RSA verifier, or
replay-protected signed-evidence contract suitable for reuse.

## Canonical readiness truth

Schema: `ATLASQUANT_AION_PROVENANCE_TRUST_READINESS_V1`

Current state is always:

- `state=BLOCKED`
- `origin_authenticated=False`
- `snapshot_signed=False`
- `signature_verification_available=False`
- `trust_root_configured=False`
- `signing_scheme_configured=False`
- `verifier_policy_configured=False`
- `replay_protection_configured=False`
- `rotation_revocation_policy_configured=False`
- `execution_allowed=False`

Canonical blockers:

1. `TRUST_ROOT_NOT_CONFIGURED`
2. `SIGNATURE_SCHEME_NOT_CONFIGURED`
3. `VERIFIER_POLICY_NOT_CONFIGURED`
4. `REPLAY_PROTECTION_NOT_CONFIGURED`
5. `ROTATION_REVOCATION_POLICY_NOT_CONFIGURED`

## Authority boundary

Caller dictionaries, runtime claims, nested snapshot claims, consistency
envelopes and forged readiness objects have zero authority to remove blockers or
promote the state.

The preflight performs no I/O, does not load keys, does not contact providers and
does not verify signatures. It exposes readiness truth only.

A healthy and globally consistent Core can therefore correctly show:

`health=CONFIRMED · consistency=CONFIRMED · provenance_trust=BLOCKED`

These are independent dimensions.

## What V2.10 intentionally does not implement

- private/public keys;
- signing or verification;
- PKI, KMS or HSM;
- Windows Hello/FIDO2/WebAuthn;
- trust-anchor enrollment;
- attestation;
- replay caches or nonce persistence;
- rotation/revocation storage;
- remote provider calls;
- execution authority.

## Future promotion requirements

A future change may only move this preflight away from BLOCKED after separately
reviewed contracts define and test at least:

- trust-root ownership and enrollment;
- canonical signed payload and signature algorithm;
- key/signer identity semantics;
- verification policy and failure behavior;
- replay/nonce/timestamp rules;
- rotation, revocation and compromise recovery;
- explicit relationship to approval authority;
- offline behavior and deterministic audit evidence.

Until then, hashes remain change-detection evidence, not signatures, and source
references remain descriptors, not authenticated origin.

Draft only. No merge, deploy, provider activation, billing, paid API, real order,
external execution or auto-repair.
