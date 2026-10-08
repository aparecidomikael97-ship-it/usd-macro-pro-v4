# AION Publisher Key Registry + Independent Build Witness — CI V1

**Date:** 2026-10-08  
**Status:** IMPLEMENTATION SAFE / SYNTHETIC TRUST ONLY / DRAFT / CI-ONLY  
**Stacked on:** #1065 Signed Release Provenance CI Fixture V1

## Goal

Separate three roles that must never be conflated in a future official
AION release: the **publisher key** signing release artifacts; the
**governance authority** approving or revoking eligible publisher keys;
and a **build witness** attesting the independently observed origin of
the specific build. A success under CI-generated keys does not establish
production identity or independence.

This V1 uses **three distinct ephemeral Ed25519 private keys generated
inside isolated CI test-process memory**. No production certificate, HSM,
FIDO2, Windows Hello, signing secret, deployed artifact or owner device is
used or modified. The implementation contains verification code only;
key generation and signing occur exclusively in adversarial tests.

## A. Signed publisher registry snapshots

A candidate registry snapshot includes:
- `ci-reg-*` registry ID and monotonic integer sequence;
- digest of previous registry snapshot (for external chain anchoring);
- issuer-policy, independent governance public-key digest, and fresh
  registry challenge;
- 1 to 8 sorted key records with unique key IDs and public-key digests;
- per-key status `ACTIVE`, `RETIRED` or `REVOKED`;
- activation and revocation sequence boundaries;
- explicit rotation-parent key relationship;
- strict false flags for production key import, real governance
  authority and HUMAN_OWNER installation authorization.

The snapshot is verified cryptographically against a **caller-provided**
governance public key and a detached Ed25519 signature. External policy
inputs must match its registry ID, expected sequence, previous-snapshot
digest, challenge, governance key digest and publisher policy.

**A valid detached signature does not mean the governance key is trusted.**
There is no production-approved root key, real monotonic durable counter,
authentic key registry, revocation broadcast or independent proof of
registry continuity in this implementation.

Test rules reject duplicate key IDs/fingerprints, two active keys, no active
key, reactivation of revoked signer, revocation before activation,
invalid rotation ancestry, future activation and malformed records.

Important production requirement: revocation must be evaluated relative
to an externally authenticated time/sequence with a real chain of
authoritative snapshots, including anti-rollback and nonce uniqueness.
These are **not** established by CI. A claimed prior digest/sequence is
not evidence of a genuine previous registry record.

## B. Separate synthetic build witness

The witness statement is signed with a **third, separate CI key** and binds:
- exact registry snapshot digest, sequence and active publisher key digest;
- #1065 release candidate digest, signed manifest hash, exact file table;
- claimed source commit, build workflow and run ID;
- build environment and release challenge;
- a distinct witness challenge and witness-key fingerprint;
- explicit false flags for true independence, verified SLSA attestation
  and production release approval.

The verifier checks actual Ed25519 signature bytes against the
caller-supplied witness public key; this key must differ from both
publisher and governance fingerprints. A witness referring to a
different release, manifest, registry, public key, commit or build ID fails.

**The witness is not independently authoritative** merely because its
key differs from the publisher's. In real production, independent
trust roots, provenance from a controlled builder, signed provenance
envelopes with verified workflow identity and permission boundaries,
artifact-subject hashes, policy-specific verification and replay
controls must be established separately.

This is **not** SLSA/in-toto provenance verification and does not assert
that the claimed GitHub run actually produced the claimed bytes.

## C. Cross-proof review and trust ceiling

The review requires the full registry candidate, separate witness
candidate and release candidate to agree on registry sequence, publisher
fingerprint, file table, manifest, source commit and build run. It
recomputes the signed candidate envelope digests, and rejects false
claims of externally verified status.

Maximum review status:
`READY_FOR_PUBLISHER_GOVERNANCE_AND_BUILD_WITNESS_SECURITY_REVIEW`.

This means the **CI fixtures and verification rules are testable**. It
does not approve a publisher, create a real independent witness, authorize
a package, measure a real Windows installation, or issue a real AION
release certificate. No real owner authorization is consumed.

## Safety / non-actions

- No production key generation or import.
- No real AION binary, package, signing or build.
- No real owner device, local agent, Windows registry, ACL, startup,
  service, process, webcam, microphone or reboot.
- No actual persistent publisher-key registry or root of trust.
- No real build/CI workload attestation, artifact publication, production
  release/revocation status or verified cryptographic independence.
- No merge, deploy, Worker activation, real install, rollback or runtime
  persistence activation.

## Verification and adversarial cases

CI runs the narrow tests on Linux and Windows with isolated ephemeral
keys; checks include invalid governance signature, self-trusted key,
sequence rollback, revocation reactivation, duplicate active keys,
missing/duplicate/unsorted registry identities, improper rotation
parents, witness public-key reuse, stale signed witness, mismatched
source/run/release manifest/registry/subject, forged SLSA claims,
altered proofs and attempted installation authorization.

No private key bytes are printed, written, checked in or transmitted.

## Next separately approved design gate

**Publisher Governance Root Anchoring + Build Attestation Identity V1**:
a reviewer-approved external root/key rotation plan, independent identity
model for production builder/witness and verifiable SLSA/in-toto statement
policy tied to exact real AION package bytes. Readiness to implement
that policy is not an authorization for production signing or deployment.
