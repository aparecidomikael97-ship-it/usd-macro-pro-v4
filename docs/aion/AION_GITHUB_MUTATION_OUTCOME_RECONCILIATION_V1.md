# AION GitHub Mutation Outcome Reconciliation V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Scope: reconciliation of GitHub mutation receipts whose primary outcome is OUTCOME_UNKNOWN  
GitHub queried by this module: NO  
Repository mutation replayed: NO  
Automatic retry: NO

## Objective

Resolve an already-recorded `OUTCOME_UNKNOWN` without rewriting history and
without replaying the repository mutation.

The original primary outcome receipt remains immutable.

Reconciliation creates a separate append-only record.

## Allowed reconciliation results

Exactly three states exist:

- `RECONCILED_CONFIRMED_SUCCESS`
- `RECONCILED_CONFIRMED_TERMINAL_FAILURE`
- `STILL_OUTCOME_UNKNOWN`

## Reconciliation only applies to UNKNOWN

A primary receipt already classified as confirmed success or confirmed terminal
failure is not eligible for this reconciliation ceremony.

The input must be a valid immutable primary receipt with:

`outcome=OUTCOME_UNKNOWN`

and automatic retry already disabled.

## Separate HUMAN_OWNER authorization

Reconciliation requires a new authorization ceremony separate from the original
mutation authorization.

The authorization binds:

- original outcome receipt digest;
- execution attempt ID;
- PR number;
- requested mutation;
- request correlation;
- idempotency key;
- effect key;
- owner subject and binding;
- owner signing-key fingerprint;
- fresh nonce;
- explicit AUTHORIZE or DENY reconciliation decision;
- bounded issue/expiry timestamps.

Maximum authorization window:

`120 seconds`

A DENY decision blocks reconciliation.

Authorization reuse is forbidden.

## Authoritative evidence

This module never performs a GitHub query.

A future trusted evidence collector may externally attest evidence classes such
as:

- GITHUB_PR_STATE_READBACK
- GITHUB_BRANCH_BASE_READBACK
- GITHUB_MAIN_COMMIT_GRAPH_READBACK
- GITHUB_MERGE_COMMIT_READBACK
- GITHUB_REPOSITORY_AUDIT_EVENT
- IMMUTABLE_REPOSITORY_OBSERVATION

The evidence must bind the original receipt and exact attempt.

## Exact correlation requirements

Evidence must match:

- repository identity;
- PR number;
- requested mutation;
- execution attempt ID;
- request correlation;
- idempotency key;
- effect key.

Evidence must also be:

- source-attested;
- schema-valid;
- authentic;
- fresh;
- sequence/version monotonic;
- based on independent repository readback.

Evidence older than 120 seconds is rejected by this V1 evidence boundary.

## Mutation-specific success proof

Success evidence is not generic.

### PR_DRAFT_TO_READY

Requires authoritative PR-state readback.

### PR_RETARGET_TO_MAIN

Requires:

- PR-state readback;
- branch-base readback.

### SQUASH_MERGE_TO_MAIN

Requires:

- PR-state readback;
- main commit-graph readback;
- merge-commit readback.

This prevents a generic “looks okay” observation from becoming reconciled
success.

## Confirmed no-effect proof

For a reconciled no-effect result:

### PR_DRAFT_TO_READY

Requires PR-state readback.

### PR_RETARGET_TO_MAIN

Requires PR-state + branch-base readback.

### SQUASH_MERGE_TO_MAIN

Requires PR-state + main commit-graph readback.

A terminal-rejection reconciliation additionally requires authoritative audit or
immutable repository evidence.

## RECONCILED_CONFIRMED_SUCCESS

Success is allowed only when:

- all correlation checks pass;
- evidence is complete;
- mutation-specific success evidence is present;
- the expected repository postcondition is authoritatively verified;
- no failure/no-effect signal conflicts with success.

## RECONCILED_CONFIRMED_TERMINAL_FAILURE

Terminal failure is allowed when authoritative evidence proves either:

- the effect did not happen; or
- an authoritative terminal rejection occurred.

Even a confirmed no-effect state does not automatically authorize retry.

It only allows a future new attempt to be considered after a complete new owner
authorization ceremony.

## STILL_OUTCOME_UNKNOWN

Unknown is preserved whenever evidence is:

- missing;
- incomplete;
- stale;
- unauthenticated;
- weakly correlated;
- conflicting;
- sequence-regressed;
- inconsistent with repository postcondition.

Success and failure signals present at the same time force
`STILL_OUTCOME_UNKNOWN`.

## No retry during reconciliation

Reconciliation is not a retry.

The original repository mutation is never replayed by this layer.

All reconciliation records keep:

- automatic_retry_allowed=false
- retry_scheduled=false
- retry_performed=false
- new_attempt_authorized=false

A future new attempt requires:

- fresh HUMAN_OWNER authorization;
- a new effect key;
- a new execution attempt ID.

## Original receipt is immutable

Reconciliation never changes:

`OUTCOME_UNKNOWN`

inside the original receipt.

Instead it appends a separate reconciliation record linked by digest.

This preserves the historical truth that the original call outcome was unknown
at the time it was recorded.

## Explicitly absent

This V1 does not:

- query GitHub;
- open network transport;
- repeat the repository mutation;
- mark a PR Ready;
- retarget/rebase;
- merge;
- close a PR;
- delete a branch;
- deploy;
- activate Worker/provider/production persistence;
- authorize a new attempt.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_GITHUB_MUTATION_OUTCOME_RECONCILIATION_V1_CONTRACT_VALIDATED`

No repository query or mutation is implied.
