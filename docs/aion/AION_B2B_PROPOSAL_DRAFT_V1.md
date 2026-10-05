# AION B2B Proposal Draft V1

Status: **staging / non-binding / human-authored commercial terms**.

## Objective

Create a preliminary proposal draft only after:

- a complete B2B Diagnostic Intake; and
- a positive Pilot Readiness result that is still awaiting owner review.

The proposal builder does not replace owner approval, contract review, pricing
approval or customer communication.

## Identity binding

The proposal binds:

- trusted owner / tenant / workspace;
- diagnostic candidate ID;
- Pilot Readiness candidate ID;
- diagnostic digest;
- Pilot Readiness evidence digest.

A candidate or scope mismatch blocks the proposal.

## Packages

V1 supports the existing commercial package names:

- ESSENCIAL;
- PROFISSIONAL;
- COMPLETO.

No package is selected automatically.

## Human commercial terms

A draft requires:

- `human_terms_confirmed=true` exactly;
- human commercial author reference;
- proposal ID;
- package;
- at least three scope items;
- at least two exclusions;
- at least two implementation phases;
- at least two assumptions;
- at least two proposal evidence refs;
- explicit non-binding status;
- validity window.

Truthy strings do not count as human confirmation.

## Pricing modes

### TBD

No setup or monthly price may be present.

### INDICATIVE

Requires explicit human-provided:

- indicative setup fee;
- indicative monthly fee;
- pricing basis reference.

Indicative prices are always marked `binding=false`.

The module never derives price from ROI, company size, diagnostic pain, package
name or any other inferred attribute.

## Diagnostic reuse

The draft can carry forward:

- objectives;
- quick-win candidates;
- diagnostic constraints.

It does not copy raw lead/contact identity into the proposal object.

## Pilot Readiness reuse

The proposal requires:

- schema `ATLASQUANT_AION_B2B_PILOT_READINESS_V1`;
- state `READY_FOR_OWNER_REVIEW`;
- decision `PILOT_REVIEW_CANDIDATE`;
- owner-decision boundary present;
- no readiness blockers;
- candidate ID match;
- tenant/workspace match;
- readiness evidence digest.

## Output state

A valid proposal is only:

`DRAFT_FOR_HUMAN_REVIEW`

It is not customer-sendable and it is not a contract.

## Negócios cockpit

The existing **Propostas** route may render a valid proposal draft in read-only
mode.

The cockpit exposes only:

- proposal ID;
- package;
- pricing mode;
- indicative setup/monthly values when explicitly present;
- validity window;
- scope count and scope items;
- implementation phase count.

The UI requires all non-binding/non-execution flags to remain safe before
rendering.

Any unsafe flip such as `customer_send_allowed=true`,
`contract_ready=true`, `price_commitment=true`, automatic pricing/contact,
CRM write or `executes_action=true` causes the proposal view to fail closed
back to preview mode.

The proposal surface contains no send, sign, charge, pay or contract-generation
control.

## Safety boundary

The draft never:

- sends itself to a customer;
- commits a price;
- signs or activates a contract;
- bills or charges;
- provisions an account;
- writes CRM data;
- calls a provider;
- deploys;
- mutates production.

`customer_send_allowed=false`.
`contract_ready=false`.
`price_commitment=false`.
`automatic_customer_contact=false`.
`automatic_billing=false`.
`executes_action=false`.
