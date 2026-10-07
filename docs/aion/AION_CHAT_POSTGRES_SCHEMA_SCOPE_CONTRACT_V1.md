# AION Chat — Postgres Schema & Scope Contract V1

## Purpose

Define the minimum relational isolation model for a future production AION Chat
Postgres adapter without executing SQL or creating a database.

This contract follows the evidence mapping in #981 and the storage attestation
requirements in #978.

## Required tables

- `chat_conversations`
- `chat_messages`
- `chat_attachment_metadata`
- `chat_access_audit`

These are logical table roles, not an applied migration.

## Scope boundary

Every durable chat record must be bound to:

- `owner_id`
- `tenant_id`
- `workspace_id`

Scope columns are mandatory, non-null and indexed as part of a composite scope
key. Conversation/message/attachment/audit access must always include the
authenticated scope.

No global unscoped conversation or message lookup is allowed.

## Defense in depth

Future production Postgres should use:

1. application-level authenticated scope checks;
2. parameterized queries only;
3. a least-privilege, non-superuser application role;
4. PostgreSQL row-level security as defense in depth;
5. forced RLS where the final migration design safely permits it.

RLS does not replace application scope validation.

## Conversation and message invariants

- conversation identity is unique inside its owner/tenant/workspace scope;
- messages cannot reference a conversation from another scope;
- message IDs are immutable;
- sequence ordering is explicit and deterministic;
- idempotency keys are required for durable append;
- retention/deletion is policy-controlled rather than ad hoc.

## Attachments

Production chat continues the existing metadata-only attachment model.

Binary attachment objects do not belong inside the chat relational schema in
this contract.

## Audit

Audit rows are scope-bound and operational.

Audit records must not copy message body content. They may record internal IDs,
operation type, actor/scope identifiers, result, timestamp and evidence digests.

## Secrets

The chat database never stores:

- model/provider API keys;
- Postgres credentials;
- signing private keys;
- HUMAN_OWNER cryptographic private material.

## Maximum state

`READY_FOR_POSTGRES_SCHEMA_SCOPE_DESIGN_REVIEW`

## Next allowed step

`DESIGN_POSTGRES_MIGRATION_AND_HEALTH_FAIL_CLOSED_CONTRACT`

No database connection, SQL execution, migration, billing, deploy or Worker
authority is granted.
