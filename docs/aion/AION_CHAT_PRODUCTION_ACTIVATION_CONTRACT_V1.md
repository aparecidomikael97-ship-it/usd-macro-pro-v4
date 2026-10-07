# AION Chat — Production Activation Contract V1

## Purpose

Define the fail-closed evidence boundary that must be satisfied before a future
production host can connect the AION chat UI to a real model response path.

This contract is **design/CI-only**. It does not activate a provider, read a
secret, create a production database, execute billing, write the Core, deploy,
arm a Worker or perform an external action.

## Existing pieces reused

The repository already contains:

- authenticated AION chat UI;
- verified local READ/SEARCH Golden Path;
- durable staged chat foundation and scoped history;
- provider-neutral model gateway;
- OpenAI adapter with privacy, pricing, budget and explicit-approval gates;
- Core/Guardian authority boundaries.

The missing piece is production composition. V1 defines its prerequisites
without implementing that composition.

## Required owner boundary

The initial production path is intentionally narrow:

- authenticated ADMIN session;
- session must be bound to `HUMAN_OWNER`;
- UI recognition is not cryptographic signing authority;
- no session-wide approval;
- no implicit approval from ordinary chat text.

## Required production storage evidence

A future production chat store must prove:

- production store attested ready;
- durable history;
- owner/tenant/workspace scope binding;
- encryption at rest;
- backup + restore validation;
- schema migration validation;
- health validation.

The current local/staging SQLite host does not satisfy this production
attestation by itself.

## Model boundary

A future real response path must preserve:

- provider-neutral routing;
- healthy local fallback;
- router itself performs no provider call;
- external provider configuration ready;
- explicit external-model feature flag;
- pricing configured;
- valid model budget with positive remaining allowance;
- explicit approval for each paid external request;
- provider output remains `MODEL_OUTPUT_UNVERIFIED` until evidence supports
  stronger factual claims.

## Authority boundary

Even a READY design review keeps all execution fields false:

- no provider call;
- no network call;
- no billing execution;
- no Core checkpoint write;
- no memory promotion;
- no deploy;
- no Worker arming/activation;
- no external action;
- no trading.

A conversational model response is advisory text, not an authority token.

## Maximum state

`READY_FOR_PRODUCTION_CHAT_ACTIVATION_DESIGN_REVIEW`

The only allowed next step is:

`IMPLEMENT_PRODUCTION_CHAT_HOST_ADAPTER_IN_SEPARATE_PR`

That future adapter must remain separately reviewable and must not imply deploy.
