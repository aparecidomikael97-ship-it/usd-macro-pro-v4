# AION Managed Operations Simulation V1

Status: **offline / synthetic / Draft-only**.

## Objective

Test the operating model for AION Managed Operations before any real client pilot.
The simulation uses 3 fictional companies and exactly 1,000 deterministic tasks.

## Autonomy classes

- `AUTO_SAFE`: bounded low-risk work may be completed automatically.
- `DRAFT_FOR_HUMAN`: AION prepares the work; a human owns the final send/commitment.
- `REQUIRE_APPROVAL`: binding or high-risk work requires explicit approval.
- `HUMAN_ONLY`: judgment remains human-owned.
- `DENY`: prohibited or control-bypass activity is rejected.

## Reference workload

The workload covers CRM hygiene, lead capture, reminders, approved-KB FAQ replies,
customer-response drafts, proposal drafts, contract/price commitments, collection
actions, sensitive judgment, regulated judgment, and credential/control-bypass attempts.

The generator is deterministic, so CI reruns produce the same evidence digest.

## Metrics

The evaluator reports:

- exact task and company counts;
- autonomy-class distribution;
- AUTO_SAFE rate;
- assisted-or-auto rate;
- human-touch rate;
- synthetic classification error rate;
- unsafe escape and deny escape counts;
- manual baseline minutes/cost;
- modeled post-policy human minutes/cost;
- modeled cost per completed task;
- modeled savings and ROI;
- per-company economics;
- evidence digest.

All money values are synthetic model assumptions for comparative testing. They are not
customer forecasts, invoices, accounting results, or promises of realized ROI.

## Reference result at implementation time

For 1,000 deterministic tasks:

- 361 AUTO_SAFE;
- 180 DRAFT_FOR_HUMAN;
- 181 REQUIRE_APPROVAL;
- 186 HUMAN_ONLY;
- 92 DENY;
- 0 synthetic classification errors;
- 0 unsafe escapes;
- 0 deny escapes;
- 36.1% fully AUTO_SAFE;
- 72.2% assisted-or-auto;
- modeled cost/task: R$ 6.1679 versus R$ 12.8999 manual baseline;
- modeled savings: R$ 6,732.0433;
- modeled ROI: 109.1472%.

The only allowed positive recommendation is `HUMAN_REVIEW_CANDIDATE`.
It does not authorize a pilot, merge, deploy, customer onboarding, payment action,
provider activation, or production mutation.

## Guardrails

- synthetic_workload=true;
- customer_data_used=false;
- provider_called=false;
- external_tool_called=false;
- production_mutation=false;
- automatic_customer_commitment=false;
- payment_executed=false;
- trading_executed=false;
- merge_authorized=false;
- deploy_authorized=false;
- executes_action=false.
