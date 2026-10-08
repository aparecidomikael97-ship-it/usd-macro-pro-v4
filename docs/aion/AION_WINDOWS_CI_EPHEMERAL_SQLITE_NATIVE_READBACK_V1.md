# AION Windows CI Ephemeral SQLite Store + Independent Reopen V1

**Status:** IMPLEMENTATION SAFE — ISOLATED CI DISK TEST, NOT OWNER-PC INSTALL  
**Date:** 2026-10-08  
**Parent:** #1061 — Synthetic Durable Store + Independent Reboot Harness V1

## Scope advancement

#1061 exercised CAS and receipt readback only in memory. This V1 adds a *real*
SQLite test database on the ephemeral GitHub-hosted **Windows** Actions runner
and uses fresh SQLite connections to read the record after committing.

**This CI job does write a scratch SQLite test file to the ephemeral GitHub
runner. It does NOT write to the owner's PC, actual Windows install target,
production data store, Registry, startup entries or ACLs.**

The explicit user-approved project flow remains non-installing, non-deploying and
Draft-only. A real user-device rollout requires separate authorization.

## Test-only execution boundary

The writer constructor rejects execution unless all are true:

- native Windows Python (`os.name=nt`, `sys.platform=win32`);
- `GITHUB_ACTIONS=true`, `RUNNER_OS=Windows`;
- PR-triggered CI (`GITHUB_EVENT_NAME=pull_request`);
- `AION_CI_EPHEMERAL_DISK_TEST=1`;
- a preexisting, non-symlink `RUNNER_TEMP` directory.

It creates a unique `TemporaryDirectory` under the runner temp root, then
creates a SQLite database exclusively inside it. The test fixture destroys
that temporary tree on normal and exception exit.

**Environment variables are spoofable; they are isolation guardrails, NOT
cryptographic authorization or secure device identity.** Never package or call
this test writer as an installation consumer. No network operations are
needed by the Python source.

## Actual ephemeral disk transactions

- SQLite `BEGIN IMMEDIATE` locks a writer before comparing a global revision.
- A deterministic one-time record per installation ID is stored under a
  primary key; record binds store, nonce, plan, candidate, owner and host.
- A successful commit advances the store revision exactly once.
- Exact replay and conflicting second writes are both rejected without write.
- A stale revision is rejected and does not mutate the terminal record.
- `before_commit` injects a confirmed test-only rollback before insertion.
- `after_commit_ack_loss` commits a test-only record but reports
  `CI_EPHEMERAL_CAS_OUTCOME_UNKNOWN`; automatic retry is blocked.
- Physical close/reopen uses new independent SQLite handles. Row contents and
  stored checksum are cross-checked, and a tampered/missing record fails.
- Connection handles are closed before removing the scratch directory.

The SQLite connection requests `journal_mode=DELETE` and
`synchronous=FULL`. This is not a power-loss test and cannot prove hardware
flush correctness, crash durability or a production transactional store.

## Trust boundary

Valid synthetic receipt-envelope shapes may reach upstream
`TERMINAL_PERSISTENCE_ATTESTATION_SHAPE_READY_UNTRUSTED`, **never**
a trusted terminal certificate. Independent logical SQLite connections are not
an independently authenticated Windows verification authority.

No Windows owner SID is retrieved or signed in this V1. Owner SID / host /
manifest digests are **synthetic fixture strings**, not physical identity
measurements. This module does not probe processes, health, boot epoch, signer,
effective ACL, startup mechanism or real package integrity.

The previous #1061 in-memory reboot test remains separate and is not
presented as a physical boot or runtime validation.

## Required safety scenarios

Run the narrow Windows-only CI suite and assert: normal CAS + fresh reopen,
missing/invalid runner context, precommit rollback, acknowledgement loss,
no forward retry, duplicate/conflicting writes, stale revisions, wrong store,
tampered intents, truncated/changed records, readback mismatch, guaranteed
temporary-directory cleanup and zero production effect flags.

## Next separate security gate

A dedicated native Windows verifier consumer, not this fixture, would require:
real signed owner/SID observation; trusted package signer verification;
canonical paths/reparse-point handling; independent readback policy;
filesystem crash/fault testing; trusted boot epoch; health challenge
verification; durable revocation/nonce replay resistance; and explicit
owner approval before any real install mutation.

**Maximum state:** `READY_FOR_WINDOWS_EPHEMERAL_SQLITE_SECURITY_REVIEW`.

This does **not** mean AION is installed, Windows verified, healthy, or ready
for production; no merge/deploy/Worker activation occurs in this PR.
