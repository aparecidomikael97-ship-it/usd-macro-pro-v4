# AION B2B RevOps Read Model V1

Status: **staging / aggregate / read-only**.

## Objective

Project the B2B RevOps Foundation into the existing Negócios cockpit without
exposing raw CRM records or creating a second business interface.

The active destinations are the existing:

- Leads;
- Revenue Ops;
- CRM.

## Source

The read model accepts only an AION B2B RevOps Foundation snapshot in one of:

- READY;
- READY_WITH_REVIEW;
- PARTIAL.

BLOCKED and EMPTY sources are not renderable as validated RevOps evidence.

The source must match the trusted owner / tenant / workspace scope and preserve
all non-execution flags.

## Aggregate-only projection

The UI model can expose:

- accepted/rejected record counts;
- company count;
- duplicate-company candidate count;
- stale-record count;
- due-next-action count;
- DO_NOT_CONTACT count;
- unknown-contact count;
- contact-evidence coverage;
- next-action coverage;
- owner coverage;
- pipeline stage counts;
- review signals;
- evidence digest.

It deliberately excludes:

- raw lead records;
- lead IDs;
- company labels;
- contact references;
- owner references;
- record-level evidence refs;
- DO_NOT_CONTACT identity lists.

## UI behavior

If the read model is missing or invalid, Revenue Ops / CRM / Leads remain in
preview mode and no metric claim is rendered.

If state is READY, the cockpit labels data as validated aggregate RevOps.

If state is PARTIAL, the cockpit labels the evidence explicitly as partial.

All RevOps views continue to display EXECUÇÃO BLOQUEADA.

## Safety boundary

The read model and UI cannot:

- write CRM data;
- send outreach or follow-up;
- change stage;
- assign owner;
- commit pricing;
- commit contracts;
- call providers;
- mutate production.

`read_only=true`, `raw_records_exposed=false`,
`contact_data_exposed=false`, `grants_authority=false` and
`executes_action=false` are required before rendering aggregate metrics.
