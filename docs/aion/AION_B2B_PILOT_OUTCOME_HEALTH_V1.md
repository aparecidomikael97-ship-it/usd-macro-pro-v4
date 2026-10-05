# AION B2B Pilot Outcome & Customer Health Gate V1

Status: **staging / evidence-bound / owner review required**.

## Purpose

Evaluate what actually happened in a bounded B2B pilot after owner-approved activation
evidence exists. This layer separates modeled pre-pilot ROI from observed pilot results.

It never renews, pauses, terminates, bills, expands scope, contacts a customer, deploys,
or mutates production.

## Required evidence

The gate requires:

- exact owner/tenant/workspace binding;
- the reviewable Pilot Operating Contract;
- explicit owner activation attestation with approval reference;
- complete KPI measurements with source refs;
- adoption percentage;
- SLA attainment percentage;
- automation reliability percentage;
- evidence coverage percentage;
- manual baseline cost;
- observed operating cost;
- observed monthly infrastructure cost;
- incident counts;
- at least four evidence references.

No missing value is invented.

## Realized value

Observed savings:

`manual baseline cost - observed operating cost`

Observed ROI:

`observed savings / observed operating cost * 100`

These values are calculated only from supplied pilot evidence. They are not inherited
from the 1,000-task synthetic simulation and are not a promise of future ROI.

## Customer health score

The health score uses:

- 30% KPI target attainment;
- 15% adoption;
- 15% SLA attainment;
- 15% automation reliability;
- 10% evidence coverage;
- 15% non-negative realized ROI condition.

Decision bands:

- HEALTHY / CONTINUE_REVIEW_CANDIDATE: health >= 80 and observed ROI non-negative;
- WATCH / PAUSE_OR_REMEDIATE_REVIEW: health >= 60;
- UNHEALTHY / EXIT_REVIEW_CANDIDATE: below 60;
- EVIDENCE_INCOMPLETE: KPI evidence incomplete;
- STOP_REVIEW: critical, security, privacy, or scope incident;
- BLOCKED: malformed, missing, crossed-scope, or budget-invalid evidence.

Every positive or negative business outcome remains a human review candidate.

## Budget control

The observed infrastructure cost must remain:

1. at or below the pilot's approved contract budget; and
2. at or below the current global initial infrastructure cap of R$ 200/month.

Either breach blocks the evidence package.

## Hard-stop signals

Any of the following produces STOP_REVIEW:

- critical incident;
- security incident;
- privacy incident;
- scope breach.

STOP_REVIEW is not an automatic shutdown command. It is a mandatory human-owner
review signal.

## Safety boundary

owner_review_required=true.
automatic_renewal=false.
automatic_pause=false.
automatic_termination=false.
automatic_scope_expansion=false.
automatic_contract_change=false.
automatic_billing=false.
automatic_customer_contact=false.
automatic_deploy=false.
provider_called=false.
production_mutation=false.
executes_action=false.
