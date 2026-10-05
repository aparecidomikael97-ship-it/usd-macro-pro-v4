# AION Post-Hardening Readiness Gate V1

Status: **staging / Draft-only**.

## Purpose

Prevent the hardening program from turning a set of optimistic PASS strings
into a production-readiness claim.

This gate aggregates the current hardening line only after every stage snapshot
has an exact claim digest independently recorded as VERIFIED in the existing
append-only verification ledger.

## Required stages

V1 requires:

1. durable-task physical CAS integrity;
2. FinOps admission;
3. behavioral model/prompt evaluation;
4. incident-control authority matrix;
5. operational resilience / DR readiness.

Each stage has an expected schema and fail-closed contract fields.

## Independent proof

For each stage the gate computes:

`sha256(readiness schema + stage name + exact stage snapshot)`

The matching claim must exist in the tamper-evident verification ledger under:

`post-hardening:<stage>`

The ledger lookup also binds:

- owner;
- tenant;
- workspace;
- exact claim digest.

Therefore:

- changing a stage snapshot after verification breaks the claim binding;
- copying a verification entry from another tenant/workspace fails closed;
- tampering with the ledger chain blocks the whole readiness result;
- omitting an entry blocks the stage;
- a raw PASS/READY string is not sufficient evidence.

## Strongest possible output

The strongest state is:

`READY_FOR_HUMAN_OWNER_REVIEW`

It explicitly keeps all of these false:

- production_ready_claim;
- activation_authorized;
- merge_authorized;
- deploy_authorized;
- core_freeze_authorized;
- worker_arming_authorized;
- provider_activation_authorized;
- recovery_authorized;
- real_trading_authorized;
- payment_authorized.

Human review is a decision point, not execution authority.

## Guardrails

Draft only. No merge, deploy, freeze, provider activation, recovery, worker
arming, payment, real trading or production mutation is performed by this gate.
`executes_action=false`.
