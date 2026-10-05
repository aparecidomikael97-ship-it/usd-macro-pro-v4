# AION Chaos Engineering Campaign V1

Status: **staging / Draft-only**.

## Objective

Close the P1 chaos-engineering backlog item by exercising failure behavior in
the components that already exist. This block does not create a second
resilience core and does not inject faults into production.

Mandatory domains:

- provider;
- network;
- store;
- queue/outbox;
- tool/saga;
- agent;
- state corruption.

## Real staging drills

The test campaign proves:

- provider failure opens the existing circuit breaker and forces read-only
  posture;
- network timeout before a known effect moves the outbox to UNCERTAIN and only
  returns to RETRY after authoritative absence is reconciled;
- SQLite CAS crash before commit rolls back and reopens on the previous
  revision with integrity MATCH;
- lost queue/outbox response after a synthetic effect reconciles to CONFIRMED
  exactly once, without blind resend;
- tool failure after a prior confirmed effect moves the saga to
  COMPENSATION_REQUIRED and compensation still requires explicit human
  approval;
- agent loop/error storm recommends isolation without automatic kill/delete;
- tampered verification-ledger state breaks both ledger and Checkpoint Mestre
  integrity.

## Evidence gate

The campaign gate requires a VERIFIED policy bound to owner/tenant/workspace,
all seven domains, fresh observations, evidence refs, bounded recovery time and
explicit proof that no production mutation or external action occurred.

The strongest result is `READY_FOR_HUMAN_REVIEW`.

It never authorizes:

- production fault injection;
- production recovery;
- blind automatic retry;
- automatic compensation;
- automatic worker restart;
- external action.

## Guardrails

Draft only.
merge=false.
deploy=false.
provider/network real calls=false.
production mutation=false.
production fault injection=false.
worker arming=false.
Core Freeze=false.
real trading/payment=false.
`executes_action=false`.
