# AION Repository Mutation Terminal Audit Certificate V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Scope: immutable audit closure for one repository mutation attempt  
GitHub queried by this module: NO  
Repository mutation performed: NO

## Objective

Create one deterministic read-only certificate that binds the complete lineage
of a repository mutation attempt.

The certificate links:

1. repository-mutation authorization receipt;
2. authorization persistence attestation;
3. atomic authorization-consumption attestation;
4. executor boundary;
5. signed GitHub mutation adapter attestation;
6. external mutation-attempt observation;
7. immutable primary outcome receipt;
8. optional append-only reconciliation record.

## Certificate outcomes

Exactly three audit outcomes exist:

- `CERTIFIED_FINAL_SUCCESS`
- `CERTIFIED_FINAL_TERMINAL_FAILURE`
- `CERTIFIED_OPEN_AMBIGUOUS`

## Final success

A primary:

`CONFIRMED_SUCCESS`

or a valid:

`RECONCILED_CONFIRMED_SUCCESS`

maps to:

`CERTIFIED_FINAL_SUCCESS`

with:

`terminal_closed=true`

## Final terminal failure

A primary:

`CONFIRMED_TERMINAL_FAILURE`

or a valid:

`RECONCILED_CONFIRMED_TERMINAL_FAILURE`

maps to:

`CERTIFIED_FINAL_TERMINAL_FAILURE`

with terminal closure.

This does not authorize a new attempt.

## Open ambiguous certificate

A primary:

`OUTCOME_UNKNOWN`

with no reconciliation yet, or with:

`STILL_OUTCOME_UNKNOWN`

maps to:

`CERTIFIED_OPEN_AMBIGUOUS`

This is a valid audit certificate, but it is not terminal closure.

It reports:

- terminal_closed=false
- open_ambiguous=true
- reconciliation_required=true
- certificate_authorizes_retry=false
- certificate_authorizes_new_attempt=false

This distinction prevents the system from pretending an unresolved attempt has
been closed.

## Full lineage verification

The certificate validates digest bindings across the entire chain.

Examples:

- authorization persistence must bind the authorization receipt;
- authorization consumption must bind that same receipt;
- executor boundary must bind authorization + consumption;
- adapter attestation must bind the executor boundary;
- attempt observation must bind executor + adapter;
- outcome receipt must bind the exact attempt;
- reconciliation, when present, must bind the original outcome receipt.

PR number, mutation, execution attempt, logical operation, idempotency key and
effect key must remain consistent across the chain.

Any mismatch blocks certification.

## Historical authorization expiry

The authorization receipt is verified at its original verification timestamp.

A terminal certificate may be created after the short-lived authorization has
naturally expired.

Expiry after the attempt does not erase or invalidate historical evidence.

The certificate verifies that the authorization was valid when issued and used,
not that it remains usable now.

## Reconciliation rules

A reconciliation record is accepted only when the primary outcome was:

`OUTCOME_UNKNOWN`

A primary final success/failure cannot receive a later reconciliation record in
this V1.

The original outcome receipt remains immutable.

## Certificate evidence

Certificate construction additionally requires:

- audit-chain digest;
- evidence-bundle digest;
- rollback-plan digest;
- authenticated lineage evidence;
- complete lineage evidence;
- no unresolved lineage conflict.

## Immutability

The certificate manifest is canonical and digest-bound.

Changing a field such as revision, outcome or lineage digest invalidates the
certificate digest.

The certificate is:

- read-only;
- immutable;
- append-only evidence;
- not an execution authorization;
- not a retry token;
- not a reopen token;
- not a repository-mutation authorization.

## External persistence attestation

A ready certificate may later receive an external persistence attestation.

That attestation requires:

- exact certificate digest;
- persistence-record digest;
- writer-attestation digest;
- read-after-write;
- atomic write/CAS;
- writer identity;
- reopen consistency.

This module does not persist the certificate itself.

## Explicitly absent

This V1 does not:

- query GitHub;
- call the GitHub API;
- open network;
- retry/replay a mutation;
- create a new mutation attempt;
- mark a PR Ready;
- retarget/rebase;
- merge;
- close a PR;
- delete a branch;
- deploy;
- activate Worker/provider/production persistence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_REPOSITORY_MUTATION_TERMINAL_AUDIT_CERTIFICATE_V1_CONTRACT_VALIDATED`

No repository mutation is implied.
