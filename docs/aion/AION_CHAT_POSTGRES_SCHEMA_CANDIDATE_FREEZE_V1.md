# AION Chat — PostgreSQL Schema Candidate Freeze V1

Status: DESIGN / CI-ONLY CANDIDATE FREEZE  
Date: 2026-10-07  
Depends on: #1000 retention-controlled audited PostgreSQL stack  
Production effect: NONE

## Purpose

Freeze the exact reviewed V1 PostgreSQL migration candidate before any real
production database exists.

This is not the frozen AION Core V1. It is a separate storage-schema candidate
freeze for AION Chat.

The goal is simple: once this candidate is accepted, `0001_initial.sql` is no
longer edited in place. Any later schema change must become a new numbered
migration such as `0002_...`.

## Frozen candidate artifact

Migration:

`migrations/aion_chat_postgres_v1/0001_initial.sql`

Version:

`1`

Candidate SHA-256:

`7dd72d75365862f54c81110027430011f8ac8f81ce629f500cbbd9aa0c00c50c`

The migration runner's expected checksum must be byte-for-byte identical to the
candidate manifest checksum.

## Exact V1 schema surface

Expected tables:

- schema_migrations;
- schema_meta;
- conversations;
- messages;
- message_idempotency;
- attachments;
- checkpoints;
- summaries;
- access_audit.

The freeze also verifies the reviewed indexes/unique-constraint indexes and the
exact access-audit column surface, including:

- resource_type;
- resource_id;
- evidence_digest;
- created_at.

Unexpected tables or access-audit columns fail the candidate attestation.

## Existing security evidence reused

The freeze requires the existing migration health report to remain HEALTHY,
which already covers:

- schema version;
- migration checksum;
- required scoped constraints;
- transaction health;
- forced RLS;
- expected RLS policies.

The candidate freeze does not weaken or replace those gates.

## Immutability rule

After this candidate freeze is accepted for production preparation:

- do not edit `0001_initial.sql`;
- do not silently replace its checksum;
- do not reinterpret version 1;
- do not auto-migrate on application startup.

Any future schema evolution requires a new migration version and its own
checksum, tests, recovery plan and review.

This prevents a file named “migration 1” from meaning different things on
different databases.

## Fail-closed drift detection

Dedicated CI proves the candidate fails when:

- the migration file checksum differs;
- migration history checksum differs;
- a required index is missing;
- an unexpected table appears;
- the audited schema column surface drifts;
- migration/RLS health is not proven.

## Explicitly absent

This freeze does not:

- provision Render PostgreSQL;
- connect to production;
- load credentials;
- apply a production migration;
- enable billing;
- test provider PITR;
- deploy AtlasQuant;
- activate Global Worker;
- execute external actions;
- modify frozen Core V1.

## Maximum truthful state

After green CI:

`POSTGRES_SCHEMA_CANDIDATE_FROZEN_IN_CI`

This means the V1 schema artifact is stable enough to carry into the separately
authorized provider/migration sequence. It does not mean production storage is
ready.

## Next production-only boundary

When the HUMAN_OWNER has desktop access:

1. authenticate to Render;
2. verify current plan, exact cost and application region;
3. pass the production preflight;
4. provision the database;
5. configure private networking/TLS and production least-privilege identities;
6. establish backup/recovery evidence;
7. apply this exact V1 migration checksum;
8. attest the real connection and restore path;
9. keep deployment as a separate decision.
