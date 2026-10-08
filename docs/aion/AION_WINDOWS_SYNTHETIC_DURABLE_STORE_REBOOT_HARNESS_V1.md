# AION Windows Synthetic CAS Store + Independent Reboot Verification Harness V1

**Stage:** IMPLEMENTATION SAFE — SYNTHETIC TEST HARNESS ONLY  
**Stacked on:** #1060 Terminal Receipt Persistence + Post-Reboot Health V1  
**Date:** 2026-10-08

## Objective

Prove that the design-only contracts from #1060 behave fail-closed under
simulated commit faults, stale revisions, record tampering, owner mismatch,
incorrect startup policy, runtime health failure, or post-reboot replay.
This is a **test harness**, not a production Windows consumer.

## In-memory, not physically durable

`SyntheticCASStore` simulates a single-assignment terminal record with an
exact expected revision, record identity, installation ID, nonce, owner SID,
host, package, journal plan and candidate terminal outcome.

- No file, Windows Registry, SQLite/Postgres, volume, database, secure hardware,
  boot mechanism or service is opened or modified.
- `simulated_reopen()` deep-copies an in-memory state snapshot. This does
  **not** prove durability after process crash, power loss or physical restart.
- `apply(..., fault="before_commit")` proves only that the test fixture
  did not mutate its own object.
- `apply(..., fault="after_commit_unknown")` simulates a commit that may have
  occurred even though its acknowledgment was lost. It yields
  `SYNTHETIC_CAS_OUTCOME_UNKNOWN`, blocks automatic retries, and requires
  separate reconciliation inspection.
- A duplicate identical or conflicting terminal write cannot become a second
  mutation, and a stale revision is denied.
- `reconcile_snapshot()` does not grant retry, reset authorization or clear
  uncertainty. All evidence remains `synthetic_only=true`.

## Synthetic receipt attestation

The adapter exercises #1060
`validate_terminal_persistence_attestation_shape()` with:
- exact CAS prior/after revision envelope;
- digest-bound record, installation, nonce and owner/host;
- simulated read-after-write and deep-copy reopen;
- synthetic verifier manifest.

The adapter explicitly sets
`physical_persistence_verified=false` and
`terminal_receipt_persisted_trusted=false`.
It cannot create a real signed receipt, independent verifier certificate
or evidence of physical Windows installation.

## Independent verifier *model*, not device attestation

The injected fixture resembles the future independent Windows verifier
interface; source observations are test-controlled data, not live OS reads.
The harness compares observed fixture fields to the immutable post-reboot plan.

Checks include:
1. Terminal receipt shape bound to installation/owner/host;
2. Journal binding and chain condition;
3. Host identity and owner SID;
4. Simulated preboot/postboot epoch difference;
5. Package manifest and final target snapshot;
6. Owner ACL policy;
7. Startup entry policy;
8. Process/binary identity and version policy;
9. Runtime handshake and health;
10. Unexpected file/config mutation;
11. Fresh challenge binding.

Missing observations become `POSTREBOOT_HEALTH_OUTCOME_UNKNOWN` and block.
Simulated negative readings may produce only
`POSTREBOOT_UNHEALTHY_CANDIDATE_UNTRUSTED`.
Passing fixtures may produce only
`POSTREBOOT_HEALTHY_CANDIDATE_UNTRUSTED`.

**Never** infer actual reboot, installed package, OS security posture, health,
Windows identity trust, or physical receipt persistence.

## Adversarial test suite

Tests cover normal simulated CAS, confirmed test-only no-write, post-commit
acknowledgment loss, uncertain duplicate retry, conflicting/identical duplicate,
stale CAS revision, forged write intent, wrong store identity, simulated
memory-clone isolation, tampered record, missing runtime evidence,
verified negative runtime health, startup/ACL drift, wrong owner/host,
wrong package/version, boot epoch replay, old challenge, journal mutation,
missing record and explicit no-install invariants.

CI runs the same non-installing tests with controlled dependencies and
checks forbidden imports/side-effect primitives. Passing CI validates
**pure contract behavior**, not real Windows startup or reliability.

## Security review before a real PC consumer

The next implementation needs a separately authorized Windows test device and
all of the following:

- actual durable, crash-safe compare-and-set and authoritative CAS receipt;
- independent disk close/reopen or system restart readbacks;
- platform-authenticated Windows owner SID, binary signer, startup scope,
  and effective ACL validation;
- secure challenge/nonce generation and replay protection across boot epochs;
- signed manifest and trusted verifier identity/policy;
- Windows startup and runtime handshake that cannot be self-attested;
- timeout/reconciliation handling when a write may have occurred;
- no automatic install, rollback, reinstall or Worker activation;
- formal human approval for any real filesystem/Registry/startup mutation.

## Hard non-actions

`terminal_receipt_persisted=false`, `package_installed=false`,
`files_copied=false`, `acl_changed=false`, `startup_changed=false`,
`real_windows_reboot_performed=false`, `aion_started=false`,
`rollback_executed=false`, `deploy_executed=false`,
`worker_activated=false`.

Maximum synthetic status:
`READY_FOR_WINDOWS_SYNTHETIC_HARNESS_SECURITY_REVIEW`.
This is not readiness to install, not physical verification, and not
permission to deploy.
