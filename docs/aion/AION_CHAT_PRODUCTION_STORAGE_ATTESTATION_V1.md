# AION Chat — Production Storage Attestation V1

## Purpose

Define the evidence that a storage backend must prove before AION Chat may use
it as production durable history.

This contract is vendor-neutral and non-provisioning. It does not select a
provider, create a database, open a connection, load secrets, migrate data,
write runtime state, deploy, bill or execute external actions.

## Why this exists

Current repository evidence shows:

- AION Chat has robust local/staging SQLite durability and resilience tests.
- The generic tenant durable store supports identity binding, ACL, atomic
  writes, backup/restore and optional encryption.
- Those components explicitly remain local/staging/non-production.
- The current Render blueprint declares no persistent disk/volume.
- No remote database integration is currently present in the repository.

Therefore production history must not be inferred from local filesystem
durability.

## Required evidence

A future backend must prove all of:

- production backend designation;
- non-ephemeral durability;
- HUMAN_OWNER / tenant / workspace scope binding;
- default-deny access;
- encryption at rest;
- encryption in transit;
- backup policy;
- tested restore;
- schema migration plan;
- health checking;
- fail-closed behavior when unavailable;
- retention policy;
- auditability.

## Forbidden shortcuts

The following never satisfy production attestation:

- ephemeral runtime filesystem;
- staging-only SQLite merely copied to production;
- backup without tested restore;
- encryption-at-rest without transport protection;
- health unknown;
- implicit cross-tenant or cross-workspace access;
- vendor selection treated as proof of readiness.

## Maximum state

`READY_FOR_PRODUCTION_CHAT_STORAGE_ATTESTATION_REVIEW`

The only allowed next step is:

`SUPPLY_ATTESTED_STORAGE_TO_PRODUCTION_CHAT_ACTIVATION`

No provider/network/billing/deploy/Worker/external-action execution is granted.
