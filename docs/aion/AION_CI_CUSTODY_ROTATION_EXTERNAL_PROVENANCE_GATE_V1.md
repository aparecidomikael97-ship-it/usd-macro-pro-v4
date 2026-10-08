# AION CI — Custody, Rotation, Revocation + External Provenance Gate V1

**Scope:** DESIGN + isolated ephemeral CI cryptography  
**Parent:** #1067 Governance Root + Builder Identity Preflight  
**Date:** 2026-10-08  
**Owner workstation:** not accessed  
**Production signing keys:** not generated, imported, rotated, activated or revoked

## Objective and truth boundary

The chain through #1067 can exercise governance-root proposals and builder
identity signatures with self-provided CI keys. This V1 adds an explicit
**two-party custody rotation ceremony** and a **separate externally
specified builder provenance acceptance contract**.

Both are test fixtures. A successful signature proves control of a
caller-provided ephemeral key, not that the HUMAN_OWNER or a genuine outside
builder approved or performed a production action.

## A. Dual-control custody transition — *synthetic only*

A proposal binds an exact #1067 anchor/registry/checkpoint, an old root
fingerprint, a new distinct root fingerprint, a previous rotation digest,
consecutive sequence epochs, rotation-policy and recovery-quorum digests,
and a per-ceremony challenge. Both old and new ephemeral private keys
must sign the canonical JSON proposal, with verification under supplied
public keys.

The legacy-revoked set must be sorted, unique and carried forward
unchanged; the outgoing root is added to the revocation set. A new root
must not already be revoked. Old/new keys must differ from each other
and from the referenced custodian/governance/publisher keys. Invalid
epoch gaps, reverted revocations, unsigned mutations and false owner
approval claims are blocked.

Accepted *test* reasons: `SCHEDULED_CI_ROTATION` or
`SYNTHETIC_COMPROMISE_RECOVERY`. These labels do not trigger any real
rotation or recovery.

**Important limits:** signed previous-digest and integer epoch can be
rewritten by malicious holders of the test keys. This module has **no
authoritative monotonic persistence, quorum approval, offline key custody,
HSM, Windows Hello/FIDO2, real key registry, revocation distribution,
trusted timestamps, durable revocation checkpoint or recovery quorum**.
No real root key or token is touched.

Maximum state: `CI_CUSTODY_ROTATION_CANDIDATE_UNTRUSTED`.

## B. Externally specified build provenance acceptance — *fixture only*

The separately signed fixture references the exact #1067 builder proof
and governance anchor, including manifest/release candidate digests,
artifact-subject digest, source commit, build run ID, workflow and
workload identity digests. Callers supply **expected** issuer, audience,
repository, workflow ref, verification-policy digest and challenge.

The test verifies an ephemeral Ed25519 signature of the fixture, strict
allowlisted fields and exact matches with those expectations, and that
fixture signer cannot reuse the builder/witness/custodian key. It
refuses any claim that an authentic OIDC token, trusted builder,
SLSA/in-toto attestation, independent provenance or real artifact
verification has occurred.

The fixture uses `ci-fixture-issuer.example.invalid` and the explicit
predicate `CI_PROVENANCE_FIXTURE_NOT_SLSA_OR_INTOTO`.
These are **not** actual JWTs, DSSE envelopes, in-toto attestations or
SLSA provenance statements.

Maximum state:
`CI_PROVENANCE_SHAPE_AND_EPHEMERAL_SIGNATURE_READY_UNTRUSTED`.

## C. Cross-proof reviewer

The final reviewer uses exact proof-field allowlists and digest rehashes
to link custody, provenance, #1067 anchor and #1067 builder proof.
It rejects incorrectly asserted trust flags, external challenge/policy
mismatches, release-source mismatches, changed artifact subjects,
stale expected epochs and injected approval fields.

The following remain explicitly **false**, including after tests pass:
real-owner authentication, official publisher authorization, real build
provenance, genuine SLSA/in-toto verification, production key rotation,
durable revocation, installation approval, deployment and Worker.

Maximum state:
`READY_FOR_CUSTODY_AND_EXTERNAL_PROVENANCE_SECURITY_REVIEW`.

## Gate to *real external provenance* in a future authorized stage

An independent production verifier would need to:
- Obtain the **actual** attestation envelope and artifact bytes from a
  verified source, not merely trust labels and hashes supplied by caller.
- Verify signature/DSSE/in-toto envelope against a separate, pinned
  authority; validate certificate chain, time, issuer, audience and key
  lifecycle/revocation per an approved policy.
- Authenticate the actual builder workload identity: repository, workflow
  path and ref, event/ref restrictions, build environment and required
  Git commit, and enforce a minimum trusted provenance level.
- Check the attestation's subject digests against independently fetched
  AION release manifest and **actual package bytes** (not synthetic
  filenames, certificates or GitHub run IDs alone).
- Guard against mutable tags, fork/PR privilege contexts, key role
  collisions, replay, policy rollback, stale registry, builder identity
  spoofing and compromised or revoked attestations.
- Keep official publisher/governance key approval, retention, emergency
  revocation and HUMAN_OWNER installation consent in separate verifiable
  steps. Do not use a CI-generated ephemeral key as a trust root.

**No actual external identity token or attestation is processed in V1.**

## CI threat tests

Linux and Windows suites use only ephemeral keys generated in memory
by the test module and its #1067 fixture. Scenarios include old/new
signer substitution, modified signed ceremony, revoked-set truncation,
revocation-replay, new-key collision, checkpoint rollback, challenge
replay, wrong issuer/audience/repository/workflow and builder identity,
manifest/run/subject tampering, forged SLSA flags and proof-envelope
rehashing with incorrect cross-bindings.

CI enforces no filesystem, OS API, network, new keys or production
effects in the verification module. The repository remains Draft/CI-only.

## Hard prohibitions

No real key generation, import, rotation, revocation, activation, owner
credential/Windows Hello/FIDO2 consumption, real owner-device access,
installation, Windows Registry/ACL/startup/service changes, merge,
release publication, deploy or Worker activation.

Passing the fixture suite is not readiness to use a real production key
or install AION.
