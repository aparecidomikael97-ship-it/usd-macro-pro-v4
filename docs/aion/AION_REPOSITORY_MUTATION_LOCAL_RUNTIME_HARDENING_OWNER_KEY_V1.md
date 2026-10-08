# AION Local Repository Mutation Runtime Hardening + Owner Key Enrollment V1

Status: IMPLEMENTATION / OFFLINE LOCAL HARDENING  
Date: 2026-10-08  
Real Windows installation: NOT PERFORMED  
Real GitHub credentials: ABSENT  
Live GitHub mutation: DISABLED  
Deploy / Worker activation: NO

## Objective

Harden the executable offline runtime from #1042 for a future Windows owner
installation without enabling live GitHub writes.

This V1 adds:

- deterministic per-user Windows runtime layout;
- owner-only ACL attestation contract;
- single active HUMAN_OWNER public-key enrollment;
- exact binding between receipt, signature and enrolled key;
- signed and replay-protected kill-switch control;
- SQLite integrity/readback reporting;
- crash/restart recovery scan;
- concurrent CAS stress validation.

All durable hardening data remains in the same local SQLite runtime truth.

No second runtime database is created.

## Windows per-user layout

The future Windows target is the current owner's LOCALAPPDATA tree:

`%LOCALAPPDATA%\AtlasQuant\AION\RepositoryMutationRuntime`

The planned files include:

- `repository_mutation_runtime.sqlite3`
- `runtime.lock`
- `backups\`

V1 explicitly requires:

- current-user service mode;
- no ProgramData runtime;
- no UNC/network-share runtime root;
- no SYSTEM-account requirement.

The resolver is pure planning only and does not modify the filesystem.

## Windows ACL attestation

Before a future installer may treat the runtime location as trusted, external
Windows evidence must prove:

- current Windows user is the HUMAN_OWNER context;
- owner SID is bound by digest;
- owner has full control;
- inherited ACLs are disabled;
- broad write ACEs are absent;
- runtime process/service account is the current user.

This module validates the evidence but does not change Windows ACLs itself.

## HUMAN_OWNER public-key enrollment

The same SQLite database now stores one active public-key enrollment record.

The enrollment binds:

- owner subject;
- owner binding digest;
- device binding digest;
- public Ed25519 key;
- public-key fingerprint;
- single-use enrollment nonce digest;
- enrollment timestamp;
- physical-owner-presence attestation;
- owner-only-ACL attestation.

The private key is never generated or stored by this runtime.

V1 supports one active owner key only.

Key rotation is intentionally deferred to a separate ceremony.

A second different key is rejected with a conflict.

## Receipt + signature + enrollment identity binding

Before hardened synthetic execution, three independent identities must match:

1. fingerprint bound into the repository-mutation authorization receipt;
2. fingerprint of the verified Ed25519 signature;
3. fingerprint enrolled on the local device.

The owner subject and owner binding digest in the receipt must also match the
device enrollment.

A receipt signed by the enrolled key but claiming a different owner-key
fingerprint is blocked.

This closes a gap that existed in the base offline harness.

## Signed kill-switch control

The #1042 raw kill-switch setter remains available only as a test-harness
primitive.

The hardened control surface uses a separate owner-signed challenge.

A kill-switch challenge binds:

- action ID;
- desired enabled/disabled state;
- reason digest;
- nonce digest;
- enrolled owner fingerprint;
- exact previous kill-switch state digest;
- issue time;
- expiry time.

Maximum authorization window:

`120 seconds`

The HUMAN_OWNER signs the domain-separated challenge with the externally held
Ed25519 private key.

The local runtime verifies with the enrolled public key.

## Atomic kill-switch apply

Signature verification, nonce replay check, previous-state check, kill-switch
update and audit-record insertion are enforced in one SQLite
`BEGIN IMMEDIATE` transaction.

The operation blocks if:

- the challenge expired;
- the owner key changed;
- the signature is invalid;
- the nonce was already used;
- the action ID was replayed;
- the kill-switch state changed after challenge issuance.

The private key never enters the runtime.

## SQLite integrity report

The hardened store verifies:

- `PRAGMA integrity_check`;
- foreign-key consistency;
- WAL journal mode;
- synchronous durability level;
- runtime schema version;
- hardening schema version;
- key-enrollment presence;
- current kill-switch state;
- evidence-table counts.

The report is read-only.

It does not repair or mutate the database.

## Crash/restart recovery scan

The recovery scan is read-only and classifies persisted state.

Possible classifications include:

- UNCONSUMED_AUTHORIZATION_ACTIVE
- UNCONSUMED_AUTHORIZATION_EXPIRED
- CONSUMED_WITHOUT_ATTEMPT_EVIDENCE
- OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED
- OPEN_AMBIGUOUS_CERTIFIED_RECONCILIATION_REQUIRED
- RECONCILED_AUDIT_PENDING
- TERMINAL_AUDIT_PENDING
- CLOSED

Critical rule:

`CONSUMED_WITHOUT_ATTEMPT_EVIDENCE`

never releases the authorization and never authorizes automatic retry.

The runtime treats that state as requiring manual/reconciliation attention.

Likewise, OUTCOME_UNKNOWN never causes mutation replay.

## Concurrent CAS stress

The dedicated test launches 24 concurrent consumers against the same
authorization.

Required invariant:

- exactly one consumption succeeds;
- every other consumer is rejected as already consumed, conflicting consumption
  or CAS loss;
- the persisted record has exactly one consumed state.

This is a stronger runtime test than the earlier contract-only CAS assertions.

## Reopen durability

Owner enrollment, authorization consumption, nonce reservations and runtime
records persist across SQLite reopen.

No restart procedure clears replay protection.

## What this V1 does not do

This V1 does not:

- install a Windows service;
- modify a real Windows ACL;
- enroll through Windows Hello/FIDO2;
- generate/store the HUMAN_OWNER private key;
- implement key rotation;
- bind production GitHub credentials;
- query GitHub;
- install a live GitHub mutation adapter;
- call a GitHub endpoint;
- perform a live repository mutation;
- deploy;
- activate Worker/provider/production persistence.

## Current-user service boundary

Future Windows installation should remain per-user.

The intended service/process identity is the authorized current Windows user,
not LocalSystem/SYSTEM.

A separate installer/service-hardening phase must prove the actual process
identity and filesystem ACL on Mikael's PC.

## Security invariants

The hardening policy keeps:

- automatic_retry_allowed=false
- repository_mutation_replay_allowed=false
- live_github_state_reader_implemented=false
- live_github_adapter_implemented=false
- runtime_credential_broker_implemented=false
- real_github_credentials_loaded=false
- real_github_network_path_enabled=false
- github_api_called=false
- network_called=false
- live_repository_mutation_authorized=false
- live_repository_mutation_performed=false
- production_repository_mutation_performed=false

## Next safe phase

After this V1 is green, the next safe phase is:

`WINDOWS LOCAL SERVICE INSTALLATION BLUEPRINT + CRASH/PROCESS ISOLATION V1`

Still without live GitHub writes.

That phase should define and test:

- current-user process/service lifecycle;
- Windows startup/restart behavior;
- process singleton/lock ownership;
- clean shutdown and abrupt-process-loss recovery;
- real filesystem ACL verification on Windows;
- public-key enrollment UI/ceremony;
- backup/restore integrity;
- service health/readiness endpoint limited to localhost or IPC;
- no live GitHub credential until separately authorized.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_REPOSITORY_MUTATION_LOCAL_RUNTIME_HARDENING_OWNER_KEY_V1_VALIDATED`

This validates local runtime hardening logic on the CI host.

It does not mean the runtime is installed on the owner's Windows computer.
