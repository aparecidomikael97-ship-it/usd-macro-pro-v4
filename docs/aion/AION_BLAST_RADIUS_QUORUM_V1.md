# AION Blast-Radius + Quorum Gate V1

Status: **staging / Draft-only**.

## Objective

Close the explicit P1 backlog item that links blast-radius policy to autonomy
budget and independent review quorum.

This gate is deliberately non-authoritative. It does not execute an action and
does not let a committee of agents replace the HUMAN_OWNER.

## Blast-radius dimensions

A verified, scope-bound policy limits:

- affected tenant count;
- affected workspace count;
- affected records;
- external targets;
- financial value;
- required independent reviewers per risk level.

V1 is stricter than a generic multi-tenant policy: one candidate must remain
inside the same trusted tenant/workspace.

## Cumulative authority budget

Any external side effect or MEDIUM/HIGH/CRITICAL candidate must bring a
successful result from the existing
`ATLASQUANT_AION_CUMULATIVE_AUTHORITY_BUDGET_V1`.

The result must bind the same:

- transaction id;
- authority budget ref;
- authority-budget policy digest.

The budget itself must explicitly grant no authority and execute no action.

## Independent quorum

Reviews bind the exact candidate digest plus owner/tenant/workspace.

Accepted reviewers are distinct and may be Guardian, Shadow, Sentinel or a
human reviewer. A proposer cannot count its own review. Duplicate reviewer IDs
do not increase quorum.

**Quorum is advisory evidence only. It never replaces HUMAN_OWNER approval.**

## HUMAN_OWNER

Human-owner approval is mandatory when:

- policy requires it for the risk class; or
- the action is sensitive, including merge/deploy, secrets, payment, real
  trading, deletion, policy changes, worker enablement, production restore or
  external broadcast.

Approval is bound to the exact action id, candidate digest and trusted scope.

Even with valid approval, this gate returns only
`READY_FOR_DOWNSTREAM_EXECUTION_GATE`.

## High-risk reversibility

HIGH and CRITICAL candidates must be explicitly reversible and carry a rollback
reference before this gate can pass.

## Guardrails

- merge=false;
- deploy=false;
- provider/network=false;
- payment/trading=false;
- production mutation=false;
- automatic execution=false;
- automatic scope expansion=false;
- `execution_authorized=false`;
- `executes_action=false`.
