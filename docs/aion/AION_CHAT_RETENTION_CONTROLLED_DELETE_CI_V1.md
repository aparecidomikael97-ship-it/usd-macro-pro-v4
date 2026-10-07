# AION Chat — Retention + Controlled Delete CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: #998 audited PostgreSQL persistence  
Runtime target: disposable PostgreSQL 17 only

## Purpose

Define and prove a fail-closed retention/deletion boundary before any production
chat database exists.

The normal application role deliberately has no DELETE privilege. Deletion is a
separate protected capability with its own least-privilege role, an explicit
plan, external approval evidence, an atomic audit receipt and unknown-commit
reconciliation.

## V1 retention posture

V1 defaults to preservation:

- no automatic TTL;
- no scheduled purge;
- no batch delete;
- no delete through the normal application role;
- one conversation per protected decision;
- conversation must already be archived;
- an explicit delete plan must be generated first;
- the exact plan digest must be approved;
- execution fails closed if the plan changes;
- deletion and its audit receipt are one transaction.

This avoids inventing a retention duration before legal/product requirements
for the owner and future B2B tenants are finalized.

## Separate retention role

Disposable CI uses:

`aion_chat_retention_ci`

Required role posture:

- NOSUPERUSER;
- NOCREATEDB;
- NOCREATEROLE;
- NOREPLICATION;
- NOBYPASSRLS;
- schema USAGE only;
- conversations: SELECT + DELETE;
- messages/idempotency/attachments/checkpoints/summaries: SELECT only;
- access_audit: SELECT + INSERT;
- no UPDATE/DELETE on audit;
- no schema CREATE;
- no migration-history access.

The normal application role remains unable to DELETE conversations.

Foreign-key cascade handles the scoped child rows when the single conversation
row is deleted. The retention role itself receives no direct child-table DELETE
privilege.

## Plan before approval

`plan_delete()` is read-only.

It requires the target conversation to be archived and produces a content-free
plan containing only:

- scope;
- conversation id;
- counts of messages;
- idempotency records;
- attachments;
- checkpoints;
- summaries;
- plan version.

The canonical plan is SHA-256 digested.

Message bodies, titles, attachment names and summary content are not included.

## Explicit approval boundary

Execution requires a `RetentionDeleteRequestV1` containing:

- bounded unique request_id;
- conversation_id;
- authorized_by;
- exact decision `APPROVE_CONVERSATION_DELETE`;
- external approval evidence digest;
- expected plan digest.

For the current HUMAN_OWNER path, `authorized_by` must equal trusted
`Scope.owner_id`.

The executor does not create or fake approval evidence. It only requires a
SHA-256-shaped evidence reference from the separate owner-authorization
boundary.

Future delegated administrators require a separately reviewed actor/authority
model before they can use this path.

## Stale-plan protection

Execution runs at PostgreSQL `SERIALIZABLE` isolation without granting UPDATE
privilege to the retention role.

The conversation and child counts are reread inside that serializable
transaction before DELETE. If the resulting plan digest differs from the
approved plan digest, execution stops. A concurrent write that races the
protected delete must serialize cleanly or make the destructive transaction
fail closed rather than widening the role with UPDATE authority.

A new plan and new approval are required.

This prevents approval for one data set from silently authorizing deletion of a
different data set.

## Atomic audit receipt

Before DELETE, the same transaction inserts a
`CONVERSATION_DELETE` audit receipt.

The audit receipt uses `request_id` as its durable event id and records:

- internal conversation resource identity;
- COMMITTED result;
- content-free evidence digest.

If DELETE fails, the receipt insertion rolls back too.

If COMMIT succeeds but acknowledgement is lost, both the delete and audit
receipt remain committed.

## Unknown commit reconciliation

A destructive action must not be blindly retried after an ambiguous COMMIT.

`reconcile_delete()` checks:

1. same scoped request_id audit receipt exists;
2. operation/resource match the requested conversation;
3. result is COMMITTED;
4. evidence digest is well formed;
5. conversation is absent.

Only that combination proves COMMITTED.

Re-executing the exact same request after proven commit returns
`ALREADY_COMMITTED` and does not create a second deletion receipt.

A reused request_id for another resource fails closed.

## Audit survival

The access-audit table has no cascading foreign key back to the deleted
conversation.

Therefore the deletion evidence remains after conversation/message/attachment
rows are removed.

The audit itself stays RLS-scoped and append-only to the application/retention
roles.

## CI evidence

Tests cover:

- retention role least privilege;
- unarchived plan rejection;
- scoped content-free child counts;
- stale-plan rejection;
- owner-actor approval binding;
- child cascade + surviving delete receipt;
- unknown-commit reconciliation;
- idempotent repeated request;
- transactional rollback of audit + delete on forced DB failure;
- cross-scope plan denial;
- normal app role remains unable to delete;
- malformed request/decision/digests rejected;
- automatic/batch deletion disabled.

## Explicitly absent

This stage does not:

- define a legal retention duration;
- enable automatic deletion;
- delete production data;
- authenticate to Render;
- provision a database;
- configure credentials;
- bill;
- deploy;
- activate Worker;
- execute external actions;
- mutate Core V1.

## Maximum truthful state

After green CI:

`RETENTION_CONTROLLED_DELETE_VALIDATED_IN_CI`

This is a technical deletion-control proof, not a production retention-policy
or legal-compliance claim.

## Production boundary still pending

When the HUMAN_OWNER is at the computer, provider-specific work remains:
current plan/price/region verification, provisioning, private network/TLS,
production roles/secrets, backup/recovery evidence, protected migration, real
restore, connection attestation, and a separate deploy decision.
