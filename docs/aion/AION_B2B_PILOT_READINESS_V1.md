# AION B2B Pilot Readiness Gate V1

Status: **staging / Draft-only / no customer onboarding**.

## Objective

Convert the AION Managed Operations simulation into a controlled decision gate for
selecting the first B2B pilot candidate. This layer is decision support only: the
owner remains the final authority.

## Candidate score

The acceptance side is scored from 0 to 5 across seven dimensions:

- problem fit: 20%;
- process repeatability: 15%;
- data readiness: 10%;
- owner sponsorship: 10%;
- integration feasibility: 10%;
- expected value: 20%;
- scope clarity: 15%.

Privacy risk and operational risk are independently scored from 0 to 5. They do
not disappear inside the acceptance score: either risk reaching 4 or 5 is a hard
block.

The priority score combines:

- 75% acceptance score;
- 25% inverse risk score.

The default interpretation is:

- 75 or more: PILOT_REVIEW_CANDIDATE;
- 60 to 74.99: REVIEW;
- below 60: DECLINE.

A positive score never authorizes onboarding by itself.

## Hard blockers

The gate fails closed when any of the following is true:

- owner/tenant/workspace mismatch;
- missing candidate identity or insufficient evidence refs;
- invalid score input;
- planned monthly infrastructure above R$ 200;
- privacy risk >= 4;
- operational risk >= 4;
- Managed Operations simulation not PASS;
- fewer than 1,000 reference tasks or fewer than 3 reference companies;
- any classification error, unsafe escape, or DENY escape in the reference simulation;
- tenant isolation not passed;
- physical vault backend not passed;
- chaos campaign not passed;
- Mission Control not ready;
- approval gate not ready;
- audit receipts not ready;
- rollback not ready;
- drift state other than STABLE;
- security gate state other than PASS.

## Reference candidate

The synthetic strong candidate used in tests scores:

- acceptance: 93.0;
- risk: 20.0;
- priority: 89.75.

That reaches PILOT_REVIEW_CANDIDATE only. It still requires the human owner to
decide whether to start a controlled pilot.

## Safety boundary

This gate never:

- accepts a real customer automatically;
- rejects a real customer with an external side effect;
- signs or changes a contract;
- bills or charges;
- provisions an account;
- deploys;
- calls a provider;
- mutates customer data;
- mutates production.

human_owner_decision_required=true.
automatic_acceptance=false.
automatic_contract=false.
automatic_billing=false.
automatic_provisioning=false.
automatic_deploy=false.
provider_called=false.
production_mutation=false.
executes_action=false.
