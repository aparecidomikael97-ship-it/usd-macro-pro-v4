# AION B2B Pilot Operating Contract V1

Status: **Draft-only / owner approval required / no automatic activation**.

## Purpose

Define exactly how a controlled Managed Operations pilot may be reviewed before any
real customer activation. The contract keeps the pilot bounded by scope, time,
budget, KPIs, stop conditions, and rollback.

## Required contract

A reviewable pilot must contain:

- owner/tenant/workspace scope binding;
- pilot and candidate IDs;
- 7–30 day duration;
- monthly infrastructure cap at or below R$ 200;
- one or more explicit objectives;
- one or more quick wins;
- 3–8 KPIs with baseline, target, direction, unit and evidence source;
- at least three stop conditions;
- at least two rollback steps;
- at least three evidence references;
- upstream readiness evidence showing PILOT_REVIEW_CANDIDATE.

## KPI rules

Targets must represent a measurable improvement over baseline:

- HIGHER: target must be greater than baseline;
- LOWER: target must be lower than baseline.

A checkpoint never invents missing values. Missing or invalid measurement evidence
returns EVIDENCE_INCOMPLETE.

## Checkpoint states

- ON_TRACK: all KPI evidence exists and at least two-thirds of KPIs hit target;
- AT_RISK: all evidence exists but fewer than two-thirds hit target;
- EVIDENCE_INCOMPLETE: missing or invalid evidence;
- STOP_REVIEW: security, scope, privacy, or budget breach was reported;
- BLOCKED: the underlying contract is not reviewable.

STOP_REVIEW is not an automatic shutdown command. It is a mandatory owner review
signal; enforcement remains outside this pure decision-support layer.

## Reference KPI set used in tests

- first-response time: 30 min baseline -> 15 min target;
- on-time follow-up completion: 60% -> 85%;
- administrative time per case: 20 min -> 12 min.

These are synthetic examples, not claims about a real client.

## Safety boundary

The operating contract never:

- activates a pilot;
- signs a contract;
- contacts a customer;
- bills or spends;
- expands scope;
- deploys;
- calls a provider;
- changes production.

human_owner_approval_required=true.
activation_state=BLOCKED_UNTIL_OWNER_APPROVAL.
automatic_activation=false.
automatic_contract_signature=false.
automatic_customer_contact=false.
automatic_billing=false.
automatic_spend=false.
automatic_deploy=false.
provider_called=false.
production_mutation=false.
executes_action=false.
