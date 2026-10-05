# AION Mission Control V1

Status: **staging / Draft-only**.

## Purpose

Mission Control is a read-only administrative projection. It does not become a
new orchestrator or a new source of truth.

It consolidates six existing AION sources:

1. System Health Center;
2. FinOps metering/admission;
3. Release Confidence;
4. Post-Hardening Readiness;
5. Incident Center;
6. physical Durable Task Repository.

## Data minimization

Mission Control does not expose raw task payloads or incident payloads.

It publishes only operational aggregates such as:

- health state and unresolved-domain count;
- projected calls/tokens/cost and FinOps mode;
- evidence-confidence coverage;
- verified readiness-stage count;
- incident counts/highest severity;
- task counts by state.

FinOps, Readiness and Durable Tasks must bind the exact
owner/tenant/workspace. Health and Incident Center are treated as already
sanitized global/local administrative projections; Mission Control copies only
their aggregates.

## Overall state

- `BLOCKED`: invalid source/schema/scope/integrity, blocked/unknown health,
  FinOps block, blocked confidence, readiness not ready, or critical incident;
- `DEGRADED`: health/FinOps degraded, confidence needs evidence, noncritical
  incidents, or blocked tasks;
- `READY_FOR_HUMAN_REVIEW`: all required upstream evidence is clean.

The ready state is still only a human-review posture.

## Non-authority

Mission Control never:

- repairs or restarts a component;
- changes a budget;
- stops/re-enables a capability;
- transitions a durable task;
- merges/deploys;
- arms a worker;
- activates a provider;
- restores production;
- trades or pays.

`executes_action=false`.

## Guardrails

Draft only.
merge=false.
deploy=false.
source_of_truth=false.
projection_only=true.
raw_payloads_exposed=false.
provider/network=false.
production mutation=false.
Core Freeze=false.
worker arming=false.
real trading/payment=false.
