# AION Incident Control & Authority V1

Status: **staging / Draft-only**.

## Goal

Make incident control explicit: **who may request a shutdown, what can be
stopped, and what is required before re-enabling it**. The contract is a
decision/runbook layer only; no feature flag, process, provider, credential,
deployment, payment or trading state is mutated here.

## Capability kill switches

The matrix covers:

- global worker;
- external tools;
- model provider;
- governed memory promotion;
- external messaging;
- CRM mutation;
- payments;
- real trading;
- merge to main;
- production deploy;
- credential use.

Capabilities are classified as tenant-scoped or global and as critical or
non-critical.

## Authority

`HUMAN_OWNER` may request STOP for any listed capability only when verified
authority evidence binds the trusted owner identity and exact control capability.
A `DELEGATED_ADMIN` may request STOP only when an explicit verified capability
grant exists and only for explicitly non-critical
operational capabilities. Internal AION roles `guardian` and `sentinel`
may recommend STOP but never mutate the control.

Critical STOP remains owner-only. REENABLE is intentionally stricter than STOP:
it requires `HUMAN_OWNER`, exact owner approval, a CLOSED incident reference
and verified recovery evidence. Even then, the result only progresses to a
separate audited mutation gate.

## Runbook

For HIGH/CRITICAL incidents:

1. preserve evidence and determine affected scope;
2. obtain the authorized STOP request;
3. mutate the control only through the downstream audited gate;
4. verify no new side effects and reconcile in-flight work;
5. record cause, impact and closure evidence;
6. require owner approval plus recovery evidence before REENABLE.

## Guardrails

Draft only. No automatic containment/re-enable, merge, deploy, provider call,
credential rotation, payment, trading, Core Freeze, worker arming or production
control mutation. `executes_action=false` throughout.
