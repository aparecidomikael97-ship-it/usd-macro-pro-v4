# AION B2B Pilot Planning Handoff V1

Status: **staging / internal planning only / no activation**.

## Objective

Connect the non-binding B2B Proposal Draft to the existing controlled Pilot
Operating Contract without creating a second pilot engine.

The handoff imports and calls the existing:

`build_pilot_operating_contract(...)`

All duration, budget, KPI, stop-condition, rollback and activation-boundary
rules continue to live in that existing contract builder.

## Preconditions

The handoff requires:

- trusted owner / tenant / workspace;
- Proposal Draft in `DRAFT_FOR_HUMAN_REVIEW`;
- proposal remains non-binding;
- customer send remains blocked;
- contract readiness remains false;
- price commitment remains false;
- all proposal automatic-action flags remain false;
- Pilot Readiness remains `PILOT_REVIEW_CANDIDATE` / `READY_FOR_OWNER_REVIEW`;
- exact candidate ID match;
- exact owner / tenant / workspace match;
- exact Pilot Readiness evidence digest match between proposal and readiness.

Any mismatch blocks before the Pilot Operating Contract builder is called.

## Human planning boundary

Pilot planning terms require:

- `human_planning_confirmed=true` exactly;
- human pilot planner reference;
- pilot ID;
- duration;
- monthly infrastructure cap;
- selected pilot scope items;
- selected objectives;
- selected quick wins;
- 3–8 evidenced KPIs through the existing contract builder;
- at least three stop conditions through the existing contract builder;
- at least two rollback steps through the existing contract builder;
- planning evidence references.

Truthy strings do not count as human planning confirmation.

## No scope expansion

`pilot_scope_items` must be a subset of the proposal scope.

Pilot objectives must already exist in the proposal objectives.

Pilot quick wins must already exist in the proposal quick-win candidates.

A planning handoff cannot silently introduce a new commercial scope, objective
or quick win.

## Evidence chain

The generated operating-contract specification carries:

- proposal digest;
- Pilot Readiness evidence digest;
- human planner reference;
- pilot planning evidence refs.

The bridge then verifies that the existing operating contract preserved the
proposal digest in its evidence refs.

## Output

A valid bridge result is:

`PLANNED_FOR_OWNER_REVIEW`

The nested existing Pilot Operating Contract remains:

- state: `DRAFT_FOR_OWNER_APPROVAL`;
- activation_state: `BLOCKED_UNTIL_OWNER_APPROVAL`;
- human_owner_approval_required=true.

This is internal planning only.

## Safety boundary

The handoff never:

- activates a pilot;
- signs a contract;
- sends customer contact;
- bills or charges;
- spends automatically;
- provisions;
- deploys;
- writes CRM data;
- calls a provider;
- mutates production.

All corresponding automatic-action flags remain false.
