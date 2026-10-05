# AION FinOps Metering & Budget Gate V1

Status: **staging / Draft-only**.

Base: AION hardening line through durable-task physical CAS (#710).

## Objective

Close the FinOps HIGH from the external red-team queue without activating a
provider, billing or production execution.

The contract adds explicit metering by:

- trusted owner / tenant / workspace;
- user;
- feature;
- model;
- provider;
- calls;
- recursion depth;
- input / output / total tokens;
- predicted cost;
- observed actual cost when evidence exists.

## Admission policy

The gate consumes a VERIFIED policy bound to the same owner/tenant/workspace as the ledger. Cost, calls, tokens, recursion depth and per-user ceilings are mandatory; missing or malformed limits fail closed. The gate returns only a decision for a caller to enforce:

- `ALLOW / NORMAL`;
- `DEGRADE / LOW_COST_MODE`;
- `BLOCK / BLOCK_NEW_WORK`.

It can enforce hard ceilings for:

- predicted cost per accounting window;
- calls;
- tokens;
- recursion depth;
- calls/tokens per user;
- noisy-neighbor share.

Soft thresholds degrade before hard exhaustion.

No automatic model switch or paid fallback is performed.

## Cost reconciliation

Predicted and actual cost are kept distinct.

When both exist, divergence is measured as:

`abs(actual - predicted) / predicted`.

Default reconciliation threshold is 20%. Divergence can either degrade new
work or block it, depending on explicit policy. Missing actual cost stays
UNKNOWN; it is never fabricated.

## Idempotency and isolation

- exact replay of an event id + digest counts once;
- same event id with different payload is rejected;
- caller-claimed scope cannot override trusted scope;
- cross-tenant/workspace events are rejected before aggregation;
- noisy-neighbor policy applies to the offending user instead of silently
  exhausting other users' budget.

## Guardrails

- Draft only;
- merge=false;
- deploy=false;
- provider/network=false;
- billing/charge=false;
- automatic model switch=false;
- production persistence=false;
- worker arming=false;
- Core Freeze=false;
- trading/payment authority=false;
- `executes_action=false`.

This module is not a billing source of truth. A production release would still
need a durable metering store, provider-specific price versioning, invoice
reconciliation and operational SLO/runbook ownership.
