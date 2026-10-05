# AION B2B Pilot Planning Read Model V1

Status: **staging / aggregate / read-only**.

## Objective

Project a validated Proposal -> Pilot Planning Handoff into the existing
Negócios **Automação B2B** card without creating a new route or exposing
activation controls.

## Accepted source

The source must be an AION B2B Pilot Planning Handoff with:

- state `PLANNED_FOR_OWNER_REVIEW`;
- activation state `BLOCKED_UNTIL_OWNER_APPROVAL`;
- owner approval required;
- exact trusted owner / tenant / workspace scope;
- all automatic/external action flags false;
- handoff digest present;
- nested existing Pilot Operating Contract in `DRAFT_FOR_OWNER_APPROVAL`;
- nested activation state still blocked;
- nested automatic activation false;
- matching pilot ID and scope.

Any unsafe change fails closed.

## Aggregate projection

The read model may expose:

- pilot ID;
- proposal ID;
- planned duration;
- monthly infrastructure cap;
- number of pilot scope items;
- objective count;
- quick-win count;
- KPI count;
- stop-condition count;
- rollback-step count;
- handoff digest;
- operating-contract digest;
- blocked activation state.

## Deliberately excluded

The read model does not expose:

- candidate identity;
- company/customer identity;
- planner reference;
- proposal evidence refs;
- raw pilot evidence refs;
- KPI source refs;
- raw stop-condition content;
- raw rollback content;
- activation controls.

## Cockpit behavior

The existing **Automação B2B** route renders the planning summary only when the
read model is valid and authority-free.

The visual state remains:

`PLANEJADO · AGUARDANDO APROVAÇÃO DO PROPRIETÁRIO · SEM ATIVAÇÃO`

and the global execution indicator remains `BLOQUEADA`.

Invalid or unsafe planning state falls back to the existing preview.

## Safety boundary

The read model and cockpit cannot:

- activate a pilot;
- contact a customer;
- bill or spend;
- write CRM data;
- deploy;
- call a provider;
- mutate production;
- grant authority.

All corresponding flags remain false.
