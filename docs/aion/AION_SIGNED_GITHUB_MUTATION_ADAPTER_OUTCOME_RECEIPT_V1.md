# AION Signed GitHub Mutation Adapter + Immutable Mutation Outcome Receipt V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Scope: future repository-mutation adapter and immutable outcome classification  
GitHub API called: NO  
Network called by this module: NO  
Repository mutation performed by this module: NO

## Objective

Define the first GitHub-specific boundary after:

`READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT`

without performing the mutation.

This V1 defines a signed adapter attestation, an external attempt observation,
an immutable primary outcome receipt and fail-closed verification.

## Signed GitHub adapter

A future adapter must prove stable identity/version, exact manifest/build
digests, supply-chain evidence, repository identity, least-privilege scope,
response-schema/error-taxonomy/postcondition-policy digests, trusted signing
root and exact logical-operation binding.

The adapter must explicitly deny dangerous capabilities including repository or
branch deletion, force/reset/history rewrite, release/deploy, secret-management
writes, repository administration/transfer and protection/ruleset changes.

This contract contains no live endpoint, credential material or raw provider
request body and does not load a concrete adapter.

## External mutation-attempt observation

A future trusted adapter may provide an immutable observation binding the exact
executor boundary, adapter attestation, execution attempt, request correlation,
transport observation, provider request identity and timestamps.

This module validates that evidence only. It reports that the attempt, network
call and repository mutation were not performed by this module.

## Primary outcome states

Exactly three primary states exist:

- `CONFIRMED_SUCCESS`
- `CONFIRMED_TERMINAL_FAILURE`
- `OUTCOME_UNKNOWN`

No implicit fourth state is allowed.

## CONFIRMED_SUCCESS

Success requires provider response, correlation, authenticity, valid schema,
success semantics and authoritative repository postcondition readback.

Expected postconditions are mutation-specific:

- PR_DRAFT_TO_READY -> PR_IS_READY_FOR_REVIEW
- PR_RETARGET_TO_MAIN -> PR_BASE_IS_MAIN
- SQUASH_MERGE_TO_MAIN -> PR_MERGED_AND_MERGE_COMMIT_PRESENT_IN_MAIN

Absence of error is never success.

## CONFIRMED_TERMINAL_FAILURE

Terminal failure requires an authoritative correlated provider response and
evidence proving no effect or an authoritative terminal rejection.

Absence of response is not terminal failure.

## OUTCOME_UNKNOWN

Any ambiguity forces OUTCOME_UNKNOWN, including timeout after dispatch,
connection reset, process crash, missing/malformed response, correlation or
authenticity mismatch, schema mismatch, missing/conflicting postcondition
readback, simultaneous success/failure signals or incomplete evidence.

A claimed success/failure with incomplete proof is downgraded to
OUTCOME_UNKNOWN.

OUTCOME_UNKNOWN itself must carry a digest of ambiguity evidence.

## Immutable receipt

The primary receipt is immutable, append-only and digest-bound.

The original OUTCOME_UNKNOWN receipt is never rewritten later into success or
failure. Reconciliation must create a separate evidence-bound record.

## No automatic retry

OUTCOME_UNKNOWN always keeps:

- automatic_retry_allowed=false
- retry_scheduled=false
- retry_performed=false
- new_attempt_authorized=false

Reconciliation requires separate authorization.

A new attempt requires a fresh authorization, new effect key and new execution
attempt ID.

A timeout after a squash-merge request is therefore never blindly retried:
the merge may already have happened even if the caller did not receive a
response.

## Explicitly absent

This V1 does not generate a live GitHub request, call GitHub, open transport,
load credentials, mark a PR Ready, retarget/rebase, merge, close PRs, delete
branches, deploy, activate Worker/provider/production persistence, reconcile an
unknown result or retry a mutation.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_SIGNED_GITHUB_MUTATION_ADAPTER_OUTCOME_RECEIPT_V1_CONTRACT_VALIDATED`

No repository mutation is implied.
