# AION Chat — Storage Audit Receipts CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: #996 production-like schema binding  
Runtime target: disposable PostgreSQL 17 only

## Purpose

Add durable, content-free audit receipts to the AION Chat PostgreSQL mutation
path and prove that each receipt commits or rolls back atomically with the
mutation it describes.

This stage closes the auditability gap left after the real adapter was bound to
the production-like schema.

## Audit record

The production-like `aion_chat_v1.access_audit` table now stores:

- owner_id;
- tenant_id;
- workspace_id;
- event id;
- operation;
- actor_id;
- resource_type;
- resource_id;
- result;
- evidence_digest;
- created_at.

Resource identifiers are internal non-secret IDs. The new
`access_audit_scope_resource_v1` index allows scope-bound investigation of a
specific conversation/message/attachment/checkpoint/summary without storing
message bodies.

The initial migration SHA-256 for this child stage is:

`7dd72d75365862f54c81110027430011f8ac8f81ce629f500cbbd9aa0c00c50c`

No production database has received this migration.

## Atomicity

The real PostgreSQL backend exposes a mutation-audit hook inside the existing
database transaction.

The audited production-schema CI backend overrides that hook and inserts the
receipt before COMMIT.

Therefore:

- mutation succeeds + receipt succeeds -> both commit;
- mutation succeeds + receipt fails -> both roll back;
- COMMIT acknowledgement becomes unknown after a real commit -> both the
  mutation and receipt remain committed and can be reconciled;
- an idempotent replay does not create another message, but it may append a
  separate audit receipt recording `ALREADY_COMMITTED`.

A synthetic audit failure test proves that a message insert is not left behind
when audit insertion fails.

## Content minimization

Audit evidence is allow-listed per operation.

Allowed receipt operation classes are:

- `CONVERSATION_CREATE`;
- `CONVERSATION_UPDATE`;
- `MESSAGE_APPEND`;
- `MESSAGE_APPEND_IDEMPOTENT`;
- `ATTACHMENT_METADATA_ADD`;
- `CHECKPOINT_SAVE`;
- `SUMMARY_SAVE`.

The receipt never stores:

- message content;
- conversation titles;
- summary content;
- attachment names;
- prompts;
- passwords;
- secrets;
- tokens;
- DSNs;
- API keys.

The `evidence_digest` is a SHA-256 digest of a canonical allow-listed
operational evidence object. The raw evidence object itself is not persisted in
the audit table.

For attachment evidence, only the already-computed attachment digest, internal
ID and size are eligible.

## Actor model V1

For this owner-context stage, `actor_id` is bound to the trusted
`Scope.owner_id`.

That is valid for the current HUMAN_OWNER path being prepared.

Before delegated administrators or arbitrary collaborators are enabled in
production, actor identity must be separated explicitly from owner authority so
that the audit trail can distinguish owner, delegated admin, service identity
and other future roles. This CI stage does not claim that future delegated
actor model is complete.

## Append-only controls

The application role already has only SELECT + INSERT on `access_audit`.

It has no UPDATE and no DELETE.

Dedicated tests prove update/delete attempts fail with insufficient privilege.

RLS remains enabled and forced, so a different owner/tenant/workspace cannot
read another scope's receipts.

## Resource correlation

Unlike the earlier migration candidate, the audit table now includes
`resource_type` and `resource_id` directly. This avoids requiring operators
to reverse or guess a digest when investigating a specific internal object.

The evidence digest still binds the operation, resource identity, result and
allow-listed evidence fields.

## What is proved in CI

Dedicated tests prove:

- conversation creation emits a receipt;
- conversation archive/update emits a receipt;
- message append emits a receipt;
- duplicate idempotency emits an `ALREADY_COMMITTED` receipt without a
  duplicate message;
- unknown-commit reconciliation leaves the committed receipt intact;
- attachment/checkpoint/summary mutations emit receipts;
- audit and mutation roll back together on audit failure;
- receipts contain no supplied message/title/attachment-name secrets;
- receipt reads are RLS scope-bound;
- audit UPDATE/DELETE is denied to the application role;
- evidence contracts reject extra/content-bearing keys;
- receipt list limits are bounded.

## Explicitly absent

This stage does not:

- authenticate to Render;
- provision a production database;
- resolve a production credential;
- apply a production migration;
- test provider PITR;
- deploy AtlasQuant;
- activate Global Worker;
- call an external model;
- send external actions;
- modify frozen Core V1.

## Maximum truthful state

After green CI:

`STORAGE_AUDIT_RECEIPTS_VALIDATED_IN_CI`

This is not a claim of production storage readiness.

## Remaining production boundary

Provider-authenticated work still remains deferred until the HUMAN_OWNER is
back at the computer: plan/price/region verification, provisioning, private
network/TLS, production least-privilege identity, provider backup evidence,
protected migration, real restore evidence, connection attestation and a
separate deployment decision.
