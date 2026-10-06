# AION Chat Staged Storage Resilience V1

Status: **staging only**. This contract does not activate production persistence,
providers, network actions, workers, or authority.

## Objective

Close the operational-storage gap identified by the independent review without
creating a second persistence system. The existing scoped `SQLiteChatStore`
remains the only AION Chat durable store.

## Storage state contract

The store exposes one of four explicit states:

- `healthy`: WAL is active, the configured busy timeout is present, and deep
  integrity checks pass.
- `degraded`: the store is reachable but an operational resilience condition
  is below contract, such as bounded lock contention.
- `recovering`: reserved for a future orchestrated restore lifecycle.
- `failed`: the database cannot prove integrity or is unavailable.

The staged host accepts only `healthy`. It fails closed before rendering a
durable binding when the local store is not healthy.

## SQLite lifecycle

The existing WAL design is retained. This hardening makes the policy explicit:

- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`
- `PRAGMA wal_autocheckpoint=1000`
- write serialization through existing `BEGIN IMMEDIATE` message transactions
- startup `quick_check` + foreign-key integrity gate
- corruption never triggers silent creation of a blank replacement database

## Backup and restore

Backup is not a filesystem copy of an open SQLite file.

The approved staging path is:

1. deep health check;
2. `PRAGMA wal_checkpoint(FULL)`;
3. SQLite online backup API;
4. integrity validation of the backup;
5. atomic publication of the verified backup;
6. sidecar manifest with checksum and objectives.

Restore is:

1. validate backup before touching the target;
2. restore through SQLite backup API into a temporary file;
3. validate the restored temporary database;
4. atomically replace the target only after validation;
5. reopen and prove `healthy`.

An invalid/corrupted backup must never overwrite the current target.

## Staging recovery objectives

These are engineering targets for staged drills, not a production SLA:

- **RPO:** 300 seconds.
- **RTO:** 900 seconds.

A backup is not considered operationally trustworthy until a restore drill has
passed. Production objectives must be re-approved against the final production
store architecture.

## Authentication lifecycle

SQLite handles are authentication-scoped resources:

- logout closes all staged handles in the Streamlit session;
- user switch closes previous-scope handles;
- credential-fingerprint rotation closes and reopens the handle;
- durable data remains scoped by owner + tenant + workspace;
- re-opening a handle does not grant authority by itself.

## Required proof

The resilience test suite covers:

- WAL/busy-timeout/integrity state;
- 64 concurrent writes through independent SQLite handles with no lost messages;
- process kill during an uncommitted WAL transaction and safe recovery;
- verified snapshot backup and restore;
- corrupted-backup rejection without replacing the target;
- corrupt-database startup fail-closed;
- credential rotation and user-switch handle invalidation;
- logout cleanup hook.

## Explicitly still absent

This block does **not** claim completion of:

- production database architecture;
- tenant encryption/key management;
- outbox/external-action exactly-once semantics;
- backup crypto-shredding/LGPD deletion reconciliation;
- external-action saga compensation;
- provider/model activation.

Those remain subsequent hardening gates.
