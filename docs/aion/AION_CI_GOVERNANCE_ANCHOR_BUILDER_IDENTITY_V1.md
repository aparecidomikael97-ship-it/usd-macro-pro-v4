# AION Governance Root Anchoring + Builder Identity Preflight V1

**Status:** IMPLEMENTATION SAFE / DESIGN + SYNTHETIC CI CRYPTO / Draft only  
**Date:** 2026-10-08  
**Base:** #1066 Publisher Registry + Separate Build Witness V1

## Aim

Bridge #1066's untrusted registry-signature and separate-witness fixture
towards a future **independently approved governance root and verifiable
builder identity** without activating either in production. This module
contains verification APIs only; four/five distinct Ed25519 private keys are
generated **exclusively inside the CI tests**, kept in RAM and discarded.

A passing suite is not evidence that the real AION builder, publisher,
HUMAN_OWNER or signing key is authorized.

## A — Governance root *proposal*, not a trusted root

The CI proposal binds a governance and currently active publisher key to:
- exact #1066 registry digest and monotonic registry sequence;
- separately supplied synthetic custodian public-key digest;
- previous anchor digest and proposed checkpoint sequence;
- custodian-review policy, checkpoint policy and fresh owner challenge;
- explicit FALSE for owner-identity attestation, authoritative custodian
  review, durable anti-rollback and production-root activation.

A detached Ed25519 signature is checked under the separately supplied
ephemeral custodian key. The verifier requires the expected checkpoint ID,
sequence, prior digest, challenge, signer digest and policies.

**Limits:** Self-supplied custodian key is NOT the HUMAN_OWNER. A sequence
number or previous digest is NOT an independently durably anchored counter.
Root fingerprint and anti-rollback policy must eventually originate from
an approved out-of-band channel and be verified with authenticated,
independent evidence. Caller-supplied "external" hashes are merely input
shapes here.

## B — Builder identity *claim*, not external workload authentication

A fourth/fifth separate ephemeral CI key signs a builder statement bound
to all the following:
- governance anchor and active publisher key via #1066 registry;
- #1066 independent-witness statement digest and witness key;
- exact #1065 signed release candidate, manifest hash, file table hash,
  release identifier, source commit, run ID;
- workflow and environment digests;
- builder key fingerprint, workload-identity policy digest and intended
  workload-identity digest;
- a fresh builder challenge, and a subject digest over release artifacts;
- a `CI_SHAPE_ONLY_NOT_A_REAL_SLSA_ATTESTATION` predicate label.

A missing field, tampered detached signature, changed build run, repinned
release, faked workflow or reused custodian/publisher/witness key is blocked.

**Limits:** The builder signature is only a fixture. It is NOT a valid
GitHub OIDC identity token, actual SLSA/in-toto attestation, verified
builder permission boundary, reproducible build, timestamp, trusted issuer
or independently verified artifact download. No real identity provider or
build metadata endpoint is queried.

## C — Cross-proof review: strict fail closed

The final review checks exact allowlisted fields and false trust flags
for the registry, witness, release, anchor and builder proofs. It
recomputes candidate hashes and cross-checks registry digest/sequence,
governance/publication fingerprints, publisher, witness, anchor, source,
run, release, manifest, file table, workflow/environment and builder
subject.

A higher out-of-band minimum checkpoint sequence and expected anchor
digest must match the claimed data to satisfy *shape* review. No real
persisted anti-rollback authority is asserted.

**Maximum result:**
`READY_FOR_GOVERNANCE_ROOT_AND_BUILDER_IDENTITY_SECURITY_REVIEW`
— entirely UNTRUSTED for real device/production purposes.

### Adversarial CI

The narrow test suite runs on Ubuntu and Windows. It reuses the upstream
#1066 fixture and independently generates two more signing keys only
during tests. Cases cover tampered signed proposals and statements,
role collision, altered owner challenge, replaced source/run/manifest,
false SLSA identity, false human-owner approval, registry/witness
cross-proof drift, stale checkpoint, missing denial flags and unlisted
fields.

No key material is checked into the repo; no production keys exist
in this flow.

## Hard non-actions

- No production governance root or trusted public key installed.
- No private signing key escrow, HSM enrollment, FIDO2/Windows Hello
  action, owner credential/challenge execution.
- No production key rotation/revocation published or durably persisted.
- No real CI identity-token or in-toto/SLSA verification.
- No AION package built, signed, published, installed or run.
- No PC access, Windows filesystem/Registry/ACL/startup/service writes,
  process launch, reboot, network call, deploy, merge or Worker activation.

## Next distinct decision gate

Before real release governance, require separately approved publisher key
custody, stable independent trust anchoring and approval of an actual
build identity issuer/workload policy. A future test of genuine provenance
would need independently retrieved signed statements and artifact bytes
and must **never equate fixture evidence to production trust**.

Approval to use real devices or to create a production signing key
requires a separate explicit owner instruction.
