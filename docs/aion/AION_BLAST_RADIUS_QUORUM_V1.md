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

## Trusted reviewer assignments

A review does not count merely because it declares `independent=true`.
The caller must inject a trusted assignment table mapping reviewer principal id
to reviewer kind. The review's id and kind must match that external assignment
exactly. Self-review, duplicate principals, invented ids and role mismatch do
not count toward quorum.

Accepted reviewers are distinct and may be Guardian, Shadow, Sentinel or a
human reviewer. A proposer cannot count its own review. Duplicate reviewer IDs
do not increase quorum.

**Quorum is advisory evidence only. It never replaces HUMAN_OWNER approval.**

## Deterministic risk floor

Candidate-declared risk cannot lower the minimum implied by impact:

- any external side effect / external target => at least MEDIUM;
- any non-zero financial value => at least HIGH;
- any sensitive action => CRITICAL.

Understated risk blocks the candidate rather than silently upgrading it.

The candidate schema is closed. Unknown fields are blocked before review so an
unreviewed execution payload cannot be smuggled outside the candidate digest.

## Authority-budget scope binding

When the cumulative authority budget is required, its result must be bound to
the same owner/tenant/workspace, transaction id, budget ref and policy digest.
The budget result must explicitly state that it grants no authority, authorizes
no execution and executes no action.

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
