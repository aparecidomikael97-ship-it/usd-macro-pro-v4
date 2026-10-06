# AION B2B Pilot Owner Review Packet V1

Status: **staging / decision support only / owner undecided**.

## Objective

Consolidate the evidence required for the HUMAN_OWNER to review a planned B2B
pilot without recording an approval or triggering activation.

## Why this is separate from the existing Owner Decision mechanism

The existing AION Owner Decision Record is scoped specifically to Core Freeze
and accepts only:

- APPROVE_CORE_FREEZE;
- DENY_CORE_FREEZE.

That mechanism is not reused for B2B pilot approval because its semantic scope
is different.

The pilot packet therefore keeps:

- owner_decision=UNDECIDED;
- owner_decision_recorded=false;
- owner_approval_recorded=false;
- owner_signature_requested=false;
- owner_signature_verified=false;
- decision_mechanism_reused_from_core_freeze=false.

## Evidence chain

The packet verifies a single consistent chain across:

- trusted owner / tenant / workspace;
- Proposal Draft;
- Pilot Readiness;
- Pilot Planning Handoff;
- existing Pilot Operating Contract.

It blocks on candidate mismatch, tenant/workspace mismatch, readiness digest
mismatch, missing proposal evidence, or unsafe action flags.

## Owner review summary

The packet may summarize:

### Proposal

- proposal ID;
- company label;
- package;
- pricing mode;
- human-provided indicative setup/monthly values when present;
- pricing remains non-binding.

### Readiness

- readiness decision;
- acceptance score;
- risk score;
- priority score;
- planned monthly infrastructure.

### Pilot

- pilot ID;
- duration;
- max monthly infrastructure;
- bounded scope items;
- KPI labels / units / baseline / targets;
- stop conditions;
- rollback steps;
- activation remains BLOCKED_UNTIL_OWNER_APPROVAL.

### Evidence

- proposal digest;
- readiness evidence digest;
- pilot handoff digest;
- operating contract digest.

## Evidence minimization

The owner packet intentionally does not copy:

- KPI source refs;
- planner refs;
- raw proposal evidence refs;
- raw operating-contract evidence refs.

## Review checklist

The packet computes non-authoritative review facts:

- scope bound;
- candidate bound;
- proposal non-binding;
- readiness positive;
- activation blocked;
- stop conditions present;
- rollback present;
- KPIs present.

A green checklist does not mean APPROVED.

## Safety boundary

The packet never:

- records an owner decision;
- requests or verifies an owner signature;
- authorizes pilot activation;
- activates a pilot;
- contacts a customer;
- signs a contract;
- bills or spends;
- writes CRM data;
- calls a provider;
- deploys;
- mutates production.

All authority and execution flags remain false.
