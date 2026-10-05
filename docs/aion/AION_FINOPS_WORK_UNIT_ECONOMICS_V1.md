# AION FinOps Work-Unit Economics V1

Status: **staging / evidence-bound / read-only**.

## Objective

Measure the cost of completed work instead of stopping at raw token, call,
model or provider spend.

The layer consumes the existing AION FinOps metering ledger and explicit
work-unit records. It does not create provider usage events itself.

## Core question

The primary operational question is:

**How much evidenced operating cost was required to produce each completed work unit?**

This is intentionally different from:

- cost per token;
- cost per API call;
- cost per user;
- monthly infrastructure spend.

Those dimensions remain useful, but they do not by themselves measure delivery
efficiency.

## Work states

V1 accepts:

- COMPLETED;
- FAILED;
- CANCELLED;
- IN_PROGRESS.

A COMPLETED work unit requires:

- work_id;
- work_type;
- completed_at;
- at least one completion evidence reference.

## Cost allocation

Each accepted FinOps metering event may be allocated to at most one work unit
in V1.

If one provider charge covers several work units, upstream metering must split
that charge into explicit metering events before unit economics are computed.

This avoids hidden percentage allocation logic and keeps the evidence chain
auditable.

## Two cost views

### Direct completed-work cost

Shows cost evidence directly allocated to completed work units.

This is useful for comparing work types, but it does not include failed or
cancelled attempts.

### Fully-loaded operating cost per completed work

The confirmed fully-loaded metric uses:

**all allocated operating cost / completed work count**

Therefore failed and cancelled attempts contribute to the numerator.

This prevents a workflow with many failed attempts from appearing artificially
cheap.

## Confirmation rules

`confirmed_fully_loaded_actual_cost_per_completed_work_usd` is emitted only when:

- at least one work unit is completed;
- every completed work unit has cost evidence;
- every accepted metering event is allocated;
- predicted cost is complete;
- actual cost is complete;
- no work unit remains IN_PROGRESS in the cohort.

If any of these conditions are missing, the snapshot remains PARTIAL and the
confirmed unit-cost field is null.

Missing cost is never treated as zero.

## Snapshot states

- CONFIRMED — closed cohort with complete cost evidence;
- PARTIAL — useful evidence exists but coverage is incomplete;
- NO_COMPLETED_WORK — no completed denominator exists;
- BLOCKED — scope, schema, allocation or evidence contract is invalid.

## Tenant / workspace isolation

The metering ledger and every work unit are bound to the same trusted:

- owner_id;
- tenant_id;
- workspace_id.

Cross-scope work or ledger evidence blocks the snapshot.

## Aggregation

V1 exposes:

- total/completed/failed/cancelled/in-progress counts;
- completed work with cost evidence;
- allocated and unallocated metering events;
- cost coverage percentage;
- actual-cost coverage percentage;
- direct completed-work predicted/actual cost;
- direct observed cost per costed completed work;
- total allocated operating predicted/actual cost;
- confirmed fully-loaded actual cost per completed work;
- aggregation by work_type.

## Financial boundary

This snapshot is not a billing source of truth.

It does not:

- charge a customer;
- change pricing;
- change a budget;
- switch providers;
- buy a plan;
- renew a subscription;
- execute a payment.

All automatic financial/action flags remain false.
