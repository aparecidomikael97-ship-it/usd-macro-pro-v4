# AION B2B Pilot Value Realization & Retention Review V1

Status: **staging / evidence-bound / human review only**.

## Objective

Turn observed pilot outcomes into a business review that separates:

1. customer realized value;
2. operational pilot health;
3. AtlasQuant delivery economics.

The layer consumes the existing Pilot Outcome & Customer Health result. It does
not replace that gate and does not inherit synthetic ROI from the 1,000-task
simulation.

## Required inputs

- trusted owner/tenant/workspace scope;
- exact Pilot Operating Contract;
- evidence-bound Pilot Outcome Health result;
- one observation for every contracted quick win;
- at least two ordered value checkpoints;
- tenant-scoped commercial evidence;
- at least four commercial evidence references.

## Quick wins

Every quick win must exist verbatim in the owner-reviewed Pilot Operating
Contract. Unknown quick wins are rejected.

Each observation requires:

- achieved true/false;
- source reference;
- optional non-negative realized value.

The engine reports completion and achievement percentages separately.

## Value trend

Value checkpoints require an explicit positive integer sequence and include:

- period ID;
- observed savings;
- observed ROI;
- health score;
- source reference.

The engine sorts by sequence and classifies the trend as:

- IMPROVING;
- STABLE;
- DECLINING;
- INSUFFICIENT.

No trend is invented from a single checkpoint.

## Customer economics

From observed pilot evidence the engine may calculate:

- observed savings;
- customer fee;
- value-to-fee ratio;
- net customer value;
- whether observed savings cover the fee.

These are evidence-backed pilot results, not future promises.

## AtlasQuant unit economics

Internal commercial evidence may include:

- recognized service revenue;
- delivery labor cost;
- support cost;
- external cost;
- infrastructure cost.

The engine calculates:

- total delivery cost;
- gross margin in BRL;
- gross margin percentage.

Infrastructure evidence remains capped at R$200/month.

## Retention risk

Retention risk is a deterministic review signal from:

- customer health;
- quick-win attainment;
- value trend;
- observed ROI;
- value-to-fee coverage;
- provider margin.

Risk is labeled LOW, MEDIUM or HIGH.

This score never renews, pauses, expands or terminates a client.

## Review states

- STRONG_VALUE / EXPANSION_REVIEW_CANDIDATE;
- VALUE_CONFIRMED / CONTINUE_REVIEW_CANDIDATE;
- VALUE_AT_RISK / REMEDIATE_REVIEW_CANDIDATE;
- LOW_VALUE / EXIT_REVIEW_CANDIDATE;
- EVIDENCE_INCOMPLETE / VALUE_EVIDENCE_REVIEW;
- STOP_REVIEW / STOP_REVIEW;
- BLOCKED / BLOCKED.

An expansion candidate is possible only with strong health, strong quick wins,
improving trend, acceptable customer value, sustainable provider margin, low
retention risk and no low-value alert.

## Safety boundary

owner_review_required=true.
automatic_renewal=false.
automatic_expansion=false.
automatic_pause=false.
automatic_termination=false.
automatic_scope_change=false.
automatic_contract_change=false.
automatic_billing=false.
automatic_customer_contact=false.
automatic_provisioning=false.
automatic_deploy=false.
crm_write=false.
provider_called=false.
production_mutation=false.
executes_action=false.
