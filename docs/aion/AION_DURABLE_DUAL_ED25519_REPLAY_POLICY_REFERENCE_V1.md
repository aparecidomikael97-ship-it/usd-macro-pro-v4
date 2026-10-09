# AION durable dual Ed25519 replay / monotonic policy reference V1

Draft #1113, stacked on #1111 at exact reference
5542050a0a59a8a08221d96c0c3d1d45ca4f2a42.
Reference code and disposable hosted GitHub CI ONLY. DO NOT MERGE / DEPLOY /
INSTALL / RESUME. No owner-device operation, real key, native Windows call,
TPM, Hello, registry, firewall, Render, worker, ruleset, spending or enrollment.

## Reused contracts and inventory

- #1109: three independent roles and domain-separated canonical intent digests.
- #1110: Ed25519 public-key mathematical verification, not identity/enrollment.
- #1111: both Ed25519 role signatures on the same recomputed challenge.
- atlasquant_aion_nonce_registry.py: strict UTC fractional-second parser and
  integer-microsecond conversion reused directly. Existing BEGIN IMMEDIATE +
  synchronous FULL pattern informed the reference transaction.
- Existing PersistentNonceRegistry prunes expired claims; it cannot represent a
  permanently retained challenge lifecycle or an atomic policy/receipt binding.
  It remains untouched. The reference creates separate domain-specific tables,
  not a second generic nonce/key/enrollment authority.
- Existing UnifiedJournalStore: canonical integrity chain and fail-closed
  recovery semantics inspected; it is file-based and cannot atomically couple
  this SQLite nonce/policy transaction. It remains untouched.
- Existing taskgraph persistence rejects old revisions and mismatching equal
  revisions; the equivalent explicit equality rule is adopted for policy.
  Checkpoint expected_revision/CAS components are listed by the CI inventory.
- Full base-branch nonce/CAS/generation filename inventory is printed by CI.
  Default-branch code search had no indexed matches; that is not proof of
  absence on the stacked branch. Inventory and inspected sources delimit reuse.

No existing public verifier, role contract, installer/runtime or store is changed.

## Data and transaction model

ReferenceChallengeRegistry is created explicitly in an existing temporary fixture
directory below the runner temp root. No automatic startup wiring or production
path selection. Existing DBs open with URI mode=rw; missing DB never silently
becomes a fresh ledger. Exclusive create refuses an existing file or symlink.

Tables:
- meta: exact schema version and application-clock high-water mark.
- challenges: unique 256-bit lower-case hex nonce, immutable public binding,
  issue/expiry timestamps, explicit lifecycle state and optional receipt.
- policy: one global reference generation/digest, not a namespace chosen by keys.
- evidence: ordered digest-linked transition records.

Nonce width/uniqueness are enforced, but caller randomness is not independently
certified. Operational issuance will need an approved CSPRNG and trusted issuer.
Bindings include fixed purpose, all three role domains, the three public-key
fingerprints, policy digest and uint32 generation, collector binary hash and
canonical transcript. No private key, raw detached signature or executable input
is persisted. Hash-chain digests are unkeyed integrity checks, NOT signatures.

Every operation uses BEGIN IMMEDIATE, parameterized SQL, synchronous=FULL and
explicit close of the connection on every path. Consuming an ISSUED challenge,
its receipt, generation update and evidence/clock update commit atomically.
The state CAS must affect exactly one row. The whole bounded ledger is checked
before and after writes while holding the transaction.

State machine: absent -> ISSUED -> exactly one of CONSUMED / EXPIRED / REVOKED.
Terminal nonces are never deleted, reissued or reopened. Expiry is persisted on a
valid mathematical consumption attempt at/after expiry. No background scheduler.
Revocation is an explicit fixture-only denial operation, never authorization.
Denied attempts need not create a transition; every actual transition has evidence.

## Mathematical integration and authority ceiling

verify_and_consume_reference requires the exact reference registry type and a
closed raw signature request, not a supplied "verified" dictionary or a receipt.
The registry invokes #1111 itself, snapshots plain bounded inputs to prevent
ordinary input alias mutation, and compares against the exact issued binding.
Role/domain/key/policy/binary changes fail verification or issuance binding.

SIGNATURE_MATHEMATICALLY_VALID is distinct from NONCE_TRANSACTION_CONSUMED.
A replay may still mathematically verify but must not consume again.
OWNER_IDENTITY_TRUSTED and EXECUTION_AUTHORIZED remain false in every outcome.
A consumed reference receipt is NOT installer approval or pinned enrollment.

These remain false, even after real math and a successful SQLite commit:
owner_identity_authenticated, trusted_owner_public_key_pinned,
trusted_collector_public_key_pinned, independent_custody_verified,
hardware_antirollback_verified, p256_tpm_origin_attested,
physical_sandbox_verified, physical_network_deny_verified,
key_enrollment_authorized, installer_authorized, build_authorized,
deploy_authorized, safe_to_resume. Existing #1111 false gates also stay false.

HUMAN_OWNER_ED25519 and COLLECTOR_ED25519 must mathematically sign their OWN
domain digests using distinct supplied public keys. HOST_ECDSA_P256 is only a
bound public fingerprint and remains UNATTESTED: it cannot satisfy either role.

## Generation, clock and expiry

Generation range: exact int 0..2**32-1; bool/floats/strings/overflow invalid.
Issuance alone never advances the policy. A higher generation commits ONLY with
two valid mathematical signatures, exact issued binding and consumed nonce.
Equal generation is permitted only for the identical policy digest and a distinct
unconsumed nonce. Lower generation or equal/conflicting digest is rejected.
Concurrent updates cannot lower the stored head; old issued challenges become
unusable after a higher committed generation.

Caller timestamps must be RFC3339 UTC Z with <=6 fractional digits; comparison
uses the reused integer-microsecond parser. Positive lifetime <=300 seconds.
now must be within the issue/expiry interval. A durable watermark rejects backward
application time across process reopen, but does NOT attest wall-clock freshness.
Clock rollback with a restored entire DB defeats that watermark; a trusted clock
or independently protected time source is a future requirement. A malicious clock
can cause denial of service. Expiry times are local-issued ledger metadata; the
original #1109 signature transcript does not authenticate those times separately.

## Crash, corruption and bounds

No implicit create/repair/restore on reopen. Unknown schema/extra table, malformed
JSON, missing state/receipt/event, broken ordering/digest linkage, orphan rows,
policy/evidence/head discrepancies and corrupt/locked/read-only DB fail closed.
Bounds: 2,048 challenge rows, 8,192 evidence rows, 8KiB per parsed JSON record,
bounded input tree (256 nodes/depth8/512-char strings). No automatic eviction.

Before-commit crash rolls back nonce/receipt/generation together. Commit error
returns no consumption acknowledgment. If commit succeeds but the acknowledgment
is lost, result is conservatively blocked although the durable nonce remains
consumed: retries cannot double-consume. This is at-most-once reference state
transition, NOT distributed exactly-once execution or external action rollback.
Physical power-loss/storage-controller guarantees require independent validation;
process death plus SQLite journaling tests do not certify that hardware.

## Explicit disk/administrator antirollback limit

SQLite alone is NOT hardware/admin-resistant antirollback. Restoring a complete
pre-consumption fixture allows the same request to consume again; the adversarial
suite deliberately proves this limitation. A privileged attacker can replace,
delete, edit and fully rehash the DB or modify the trusted Python process.
The unkeyed evidence chain detects inconsistency, not authenticated provenance
against that attacker. No SOFTWARE or HARDWARE antirollback certification is made.
No generic replay_protection_verified or hardware_antirollback_verified promotion.
Reference observation is scoped to an intact trusted fixture across process restart.

## Tests and CI evidence

Dedicated matrix: windows-latest / ubuntu-latest, Python3.12,
cryptography==50.0.2 (unchanged project pin), PyYAML parser isolated to CI.
Pinned actions; contents:read; exact PR head checkout; no shared workflows edited.
Hosted disposable-runner guard runs BEFORE imports of key-generating test suites.
Temporary Ed25519 private objects remain in runner process RAM only. Public
signatures cross child stdin for process tests but are not written to DB/artifacts.
Artifact allowlist uploads public counts JSON only; no DB, payload, signature,
private object, key file or secrets artifact.

Tests cover distinct lifecycle, concurrent threads/processes, crash rollback,
uncertain commit, SQL read-only/lock/corruption, old/equal/future policy,
uint32 bounds, replay/reopen, raw mathematical false claims, key/domain/purpose
swap, unsigned/fabricated receipts and immutable stored outputs. Existing #1109
35 / #1110 27 / #1111 33 tests are run unchanged alongside the new suite.
No native owner-host tests run. Per-system pass/fail/skip counts and exact final
head/run links belong in the PR delivery report after CI finishes, not speculative
trust booleans in code or this document.

## Before first safe physical installation — still blocked

- Independently establish HUMAN_OWNER identity and pin/enroll the correct public
  Ed25519 owner key with explicit user-presence authorization.
- Independently enroll/pin the collector Ed25519 key and prove separate custody.
- Key lifecycle: compromise/revocation/rotation/loss/re-enrollment procedures.
- Verify actual HOST_ECDSA_P256 key origin, nonexportability and EK/AK/TPM2_Certify
  chain/nonce/device binding via an independent attestation verifier; an algorithm
  listing or RSA enterprise-CA evidence is not P256 attestation.
- Independently protected monotonic anchor/checkpoint (hardware or external
  witness), authenticated durable issuer/time, rollback/reinstall/restore drills.
- Signed/audited persistence provenance, authorized storage location/ACLs,
  symlink/reparse/race resistance, real fsync/power-loss/disk/backup verification.
- #1049 sandbox 12/12 and #1087 network deny 16/16 physically validated; CI does
  not prove either set of host properties.
- Reconcile package/binary provenance, signed explicit installer/build/deploy
  approval, independent review and cost decision; no automatic safe_to_resume.

## Evolution plan — no implementation or authorization here

1. Independently audit reference state machine/fault tests and trust boundaries.
2. Specify trusted issuer, public-key pins, owner consent and external monotonic
   anchor; preserve the separate mathematical/nonces/identity/authorization layers.
3. Design transactional storage service + protected authenticated receipts and
   policy-version compare-and-swap tied to independently enrolled keys.
4. Validate recovery, upgrade/rotation, revocation, power loss and DB restore
   against the external anchor in a physically approved sandbox.
5. Only after all physical gates and explicit HUMAN_OWNER authorization consider
   operational wiring/installer; do not reuse fixture status or environment flags
   as evidence of those gates.

Zero owner device security modifications, real credentials, production/worker
deployment, installer launch, merge, provider, billing, customer communication,
service contracting or permissions/ruleset changes.
