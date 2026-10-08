# AION DSSE + in-toto SLSA v1 — Independent Trust Preflight

**Status:** IMPLEMENTATION SAFE / CI ephemeral Ed25519 / Draft only  
**Date:** 2026-10-08  
**Stacked on:** #1068 Custody Rotation, Revocation + External Provenance Gate V1

## Goal and verified protocol components

This stage verifies the **actual DSSE v1 Pre-Authentication Encoding**
and a detached Ed25519 signature over an encoded in-toto Statement v1
containing a restricted SLSA Provenance v1 predicate. It also verifies
the complete subject bytes against their SHA-256 digest, and cross-binds
the claimed release/subject to #1068 synthetic custody/provenance receipts.

For reference:
- DSSE signature envelope and PAE protocol:
  https://github.com/secure-systems-lab/dsse/blob/master/envelope.proto
- in-toto Statement v1:
  https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
- SLSA Provenance v1 predicate:
  https://slsa.dev/spec/v1.2/build-provenance

`PAE(type, body) = "DSSEv1" + SP + LEN(type) + SP + type + SP + LEN(body) + SP + body`
where `LEN` is the byte length in ASCII decimal, without leading zeros.

## What this implementation *actually* validates

- Exactly one DSSE signature, base64 canonicality and matching
  payload type `application/vnd.in-toto+json`.
- 32-byte Ed25519 public key and 64-byte signature, with actual
  Ed25519 verification over the real DSSE PAE bytes.
- Strict in-memory UTF-8 JSON, duplicate-key rejection, no NaN,
  a 32 KiB payload limit, and canonical JSON fixture bytes.
- Exact in-toto Statement v1 `_type`, subject and predicate type
  `https://slsa.dev/provenance/v1`.
- A deliberately strict test-only subset of `buildDefinition` and
  `runDetails`; claimed builder ID and invocation/run ID must match
  external expected values exactly.
- Synthetic external parameters for source commit, repository, workflow
  reference, issuer, audience, challenge, governance anchor, registry,
  custody, builder receipt, prior release manifest and subject digest.
- Actual inert CI artifact bytes (up to 1 MiB) match exact signed
  `subject[0].digest.sha256` and externally expected digest.
- Cross-proof handoff with #1068 custody/provenance candidate digest
  rehash, exact field allowlists, denied trust flags, rotation epoch,
  anchored registry and source/run/release hash consistency.

The expected key fingerprint and claimed identities are supplied by the
test caller. They are **not obtained from an externally authenticated,
independent authority**.

## Limitations — what is NOT established

This module is **not** a complete DSSE or SLSA schema validator. It
intentionally allows exactly one signature/subject and a restricted
schema, whereas DSSE and SLSA support broader structures. Its stricter
canonical encoding requirement is a *fixture policy*, not a requirement
of the general DSSE standard.

A valid signature under a caller-supplied ephemeral public key **is not
a trusted external build attestation**. The following have not happened:

- No genuine GitHub OIDC JWT signature, issuer/JWKS, audience or clock
  check; no identity provider reached; no trusted workload identity.
- No Sigstore Fulcio certificate chain, Rekor inclusion proof,
  timestamp, key rotation or revocation independently validated.
- No full DSSE signature-set policy, provenance dependency semantics,
  independent builder identity or SLSA security-level assessment.
- No real AION binary/package artifact downloaded or built.
- No official AION publisher-key registry installed or anchored.
- No HUMAN_OWNER approval, device authorization, Windows installation,
  post-reboot health, production persistence or Worker activation.

All signing keys and artifact bytes are synthetic and used in RAM
by isolated GitHub Actions CI tests. No signer is production-authorized.
The module itself contains only verification, no private key generation.

**Maximum candidate:** `CI_DSSE_ED25519_SLSA_SUBSET_CRYPTO_VERIFIED_UNTRUSTED`.

**Maximum review:** `READY_FOR_REAL_DSSE_ATTESTOR_IDENTITY_SECURITY_REVIEW`.

Neither status means that an official release or real build is trusted.

## Adversarial test coverage

- DSSE PAE expected bytes, invalid payload type, duplicate signatures,
  wrong key-id hint, corrupt/noncanonical base64 and invalid signature.
- Duplicate JSON fields, noncanonical fixture JSON, wrong in-toto
  Statement/Provenance predicate type, empty/multiple subjects.
- Altered same-size subject bytes, hash/name substitution and signed
  build identity claims that disagree with external expectations.
- Wrong repository, workflow ref, OIDC-like issuer/audience, source
  commit, build run, manifest, artifact-subject digest and challenge.
- Absent or injected false trust-denial fields; rehashed but mismatched
  custody/provenance receipts and minimum external rotation epoch.

CI runs a narrow suite under GitHub-hosted Linux and Windows runners,
with read-only repository permissions, pinned toolchain dependencies
and a guard forbidding native/production effects.

## Next separately approved stage

For authentic independent evidence, design a **separate read-only
retriever/verifier** that obtains original DSSE/attestation envelopes
and *actual* release byte subjects from a trusted independent source,
authenticates source identities/keys and certificate chain per an
owner-approved policy, validates signed artifacts and counters,
and checks GitHub trusted builder identity/subject provenance.
No real production key or owner-device mutation can be inferred from
this design review.

**No merge, deploy, install, restart, Windows ACL/Registry/service/startup
change, credential consumption, or Worker activation.**
