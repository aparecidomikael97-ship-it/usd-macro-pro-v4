# AION B2B RevOps Cleanup Plan V1

Status: **staging / deterministic / human-review only**.

## Objective

Convert RevOps data-quality signals into an ordered cleanup queue without
mutating CRM data.

The planner consumes the existing RevOps Foundation snapshot. It does not
discover data independently and it does not execute remediation.

## Source requirements

The source must:

- use the RevOps Foundation schema;
- be READY, READY_WITH_REVIEW or PARTIAL;
- match the trusted owner / tenant / workspace;
- carry a snapshot digest;
- preserve every non-execution flag.

BLOCKED or EMPTY snapshots cannot generate a cleanup plan.

## Cleanup task types

### REVIEW_COMPANY_DUPLICATE

Created when several leads share the same company key.

It never merges records automatically.

### REVIEW_STALE_RECORD

Created for records outside the configured freshness window.

### REVIEW_DUE_NEXT_ACTION

Created when the next-action timestamp is due or overdue.

It does not trigger follow-up.

### REVIEW_CONTACT_EVIDENCE

Created when contact evidence is UNKNOWN.

It explicitly avoids inferring permission to contact.

### PRESERVE_DO_NOT_CONTACT

Created for DO_NOT_CONTACT records.

The task exists to preserve the suppression boundary, not to contact the lead.

### REVIEW_REJECTED_RECORDS

Created when the foundation rejected malformed or incomplete records.

Only the rejected count is copied into the task. Raw rejected payloads are not
copied into the cleanup plan.

## Determinism

Task IDs derive from task kind + stable record/company key.

The same source snapshot produces the same ordered task list and plan digest.

## Priority

V1 uses HIGH for:

- possible duplicates;
- due next actions;
- unknown contact evidence;
- DO_NOT_CONTACT preservation;
- rejected-record cleanup.

Stale-record review is MEDIUM.

Priority is a queue hint only and does not grant execution authority.

## Execution boundary

Every task has:

- human_review_required=true;
- automatic_execution=false;
- crm_write=false;
- outreach=false;
- destructive_delete=false;
- automatic_merge=false;
- executes_action=false.

The plan itself also keeps disabled:

- automatic cleanup;
- automatic merge;
- destructive deletion;
- automatic outreach/follow-up;
- stage change;
- owner assignment;
- CRM write;
- provider calls;
- production mutation.

Any later real remediation must pass the normal RevOps role check, Tool
Governance Gateway, approval requirements and receipt path.
