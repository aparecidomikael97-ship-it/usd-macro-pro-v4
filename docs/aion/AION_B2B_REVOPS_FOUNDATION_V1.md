# AION B2B RevOps Foundation V1

Status: **staging / read-only / data-quality first**.

## Objective

Create the operating foundation for AION Negócios before enabling outbound
automation or CRM mutation.

The first RevOps layer is intentionally about:

- clean CRM identity;
- tenant/workspace isolation;
- funnel stage truth;
- record ownership;
- explicit next action;
- contact-evidence state;
- duplicate detection;
- stale-data visibility;
- role eligibility.

It does not send messages or mutate an external CRM.

## Pipeline

The canonical B2B funnel is:

LEAD → DIAGNOSTIC → DEMO → PROPOSAL → CONTRACT → PAYMENT → IMPLEMENTATION →
APPROVAL → PUBLISHED → FOLLOWUP → ACTIVE_SERVICE

`CLOSED_LOST` is also supported.

No stage is advanced automatically.

## Required record identity

Each record is bound to:

- owner_id;
- tenant_id;
- workspace_id;
- lead_id;
- company_key;
- company_label;
- record_owner_ref;
- source;
- stage;
- evidence refs.

Non-terminal records also require:

- next_action;
- next_action_at.

## Duplicate handling

`lead_id` is identity-critical.

If the same lead_id arrives with a different digest, the snapshot is BLOCKED.

An exact replay is not double-counted and becomes a review warning.

Multiple leads under the same `company_key` are surfaced as duplicate-company
candidates. They are not silently merged because multiple legitimate contacts
or opportunities may exist for one company.

## Contact evidence

Contact state is one of:

- EVIDENCE_PRESENT;
- UNKNOWN;
- DO_NOT_CONTACT;
- NOT_REQUIRED.

`EVIDENCE_PRESENT` requires at least one evidence reference.

`DO_NOT_CONTACT` is preserved explicitly.

`UNKNOWN` is surfaced as a review condition.

This module does **not** certify legal permission to contact a person or company.
`legal_contact_permission_certified=false` always remains explicit in V1.

## Freshness and next actions

The audit accepts an explicit current timestamp and stale-window policy.

It reports:

- stale records;
- due next actions;
- next-action coverage;
- owner coverage;
- contact-evidence coverage.

These are read-only operational signals and never trigger outreach by themselves.

## Roles

V1 defines:

- OWNER;
- DELEGATED_ADMIN;
- SALES;
- OPERATIONS;
- VIEWER.

Role eligibility is not execution authority.

Every permission decision returns:

- `requires_live_authority_revalidation=true`;
- `grants_authority=false`;
- `executes_action=false`.

### OWNER

May be eligible for CRM operations plus price/contract commitments, but the real
action still requires the live governance/approval path.

### DELEGATED_ADMIN

May be eligible for broad CRM administration, assignment, export and outreach.

It is not eligible for owner-only price or contract commitment.

### SALES

May be eligible to read/edit CRM, change funnel stage and prepare outreach.

It is not eligible for price or contract commitment.

### OPERATIONS

May read and edit operational CRM data but does not receive commercial
commitment authority.

### VIEWER

Read only.

## Destructive deletion

Destructive CRM delete is unsupported for every role, including OWNER.

Future removal flows should use explicit deactivation/archive semantics and
separate governance if introduced.

## Snapshot states

- READY — clean dataset with no review warnings;
- READY_WITH_REVIEW — usable data with stale, due, unknown-contact or duplicate-company signals;
- PARTIAL — some records were rejected;
- EMPTY — no accepted records;
- BLOCKED — identity/scope or core dataset integrity conflict.

## V1 safety boundary

The foundation does not:

- write an external CRM;
- send outreach;
- send follow-up;
- assign an owner;
- advance a stage;
- commit pricing;
- commit a contract;
- certify legal contact permission;
- call a provider;
- mutate production.

All corresponding automatic-action flags remain false.
