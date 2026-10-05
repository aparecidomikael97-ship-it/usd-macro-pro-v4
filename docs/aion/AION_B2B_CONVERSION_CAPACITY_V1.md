# AION B2B Pilot-to-Managed-Service Conversion & Capacity Gate V1

Status: **staging / Draft-only / owner commercial approval required**.

## Purpose

Convert a healthy, evidence-backed pilot into a commercial review candidate without
allowing the system to auto-renew, auto-price, auto-contract, auto-bill or overbook
operational capacity.

## Package recommendation

The gate supports three commercial tiers:

- ESSENCIAL;
- PROFISSIONAL;
- COMPLETO.

The recommendation uses only bounded scope complexity:

- number of need tracks;
- integration count;
- channel count;
- requested capacity units.

The need tracks are:

- ATENDIMENTO_CONVERSAO;
- MARKETING_VENDAS;
- GESTAO_INTELIGENTE.

The recommendation is advisory. It never changes pricing or package automatically.

## Commercial economics

The gate calculates:

- monthly contribution = monthly price - expected monthly service cost;
- monthly gross margin percentage;
- implementation contribution = implementation price - expected implementation cost.

The minimum acceptable monthly gross margin comes from a VERIFIED commercial policy.
No hard-coded selling price is invented.

If margin is below policy or implementation contribution is negative, the result is
REPRICE_OR_RESCOPE_REVIEW.

## Capacity and concentration

The gate checks:

- active customer count versus configured maximum;
- projected capacity units versus configured maximum;
- projected portfolio utilization versus policy;
- single-customer share of total capacity versus policy.

Any capacity/concentration breach returns CAPACITY_REVIEW rather than silently
accepting the customer.

## Required upstream state

Commercial conversion is reviewable only when the prior pilot outcome is:

- state=HEALTHY;
- decision=CONTINUE_REVIEW_CANDIDATE;
- no blockers;
- no hard-stop reason;
- evidence digest present;
- owner review boundary preserved.

## Decision states

- REVIEWABLE / COMMERCIAL_REVIEW_CANDIDATE;
- COMMERCIAL_HOLD / REPRICE_OR_RESCOPE_REVIEW;
- CAPACITY_HOLD / CAPACITY_REVIEW;
- BLOCKED.

None of these decisions has external side effects.

## Safety boundary

owner_commercial_approval_required=true.
automatic_conversion=false.
automatic_package_change=false.
automatic_pricing_change=false.
automatic_contract=false.
automatic_billing=false.
automatic_provisioning=false.
automatic_customer_contact=false.
automatic_deploy=false.
production_mutation=false.
executes_action=false.
