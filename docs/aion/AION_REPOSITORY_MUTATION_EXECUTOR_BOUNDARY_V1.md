# AION Atomic Authorization Consumption + Repository Mutation Executor Boundary V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Scope: final boundary before one future repository mutation attempt  
GitHub API called: NO  
Repository mutation performed: NO

## Objective

Close the last fail-closed boundary before a future trusted adapter is allowed
to attempt exactly one repository mutation.

This V1 consumes the authorization architecture from the Repository Mutation
Authorization Receipt V1.

It does not perform the mutation.

## Preconditions

The executor boundary requires all of the following:

1. verified repository-mutation authorization receipt;
2. receipt still fresh;
3. durable receipt persistence attestation;
4. execution-time live preflight rebuild;
5. exact equality with all receipt bindings;
6. fresh execution attempt identity;
7. repository-reference digest;
8. idempotency-key digest;
9. effect-key digest;
10. lease-identity digest;
11. atomic authorization-consumption proof;
12. signed adapter;
13. least-privilege adapter scope;
14. exact repository/PR/mutation/state match.

## Execution-time rebuild

The live preflight is rebuilt immediately before consumption.

It must still match the authorization receipt on:

- PR number;
- requested mutation;
- main SHA;
- main tree SHA;
- head branch;
- head SHA;
- base branch;
- file-delta digest;
- workflow-snapshot digest;
- readiness digest;
- rollback-plan digest;
- preflight digest.

Any drift blocks.

## Fresh execution preflight

The execution-time state check is bounded to:

`15 seconds`

A stale or future-dated execution preflight blocks.

This prevents a receipt from being consumed against repository state that may
already have changed.

## Atomic authorization consumption

The first positive intermediate state is:

`READY_FOR_ATOMIC_AUTHORIZATION_CONSUMPTION`

This is only a consumption candidate.

It does not consume authorization.

A separate external durable writer must prove:

- prior state was unconsumed;
- atomic compare-and-set succeeded;
- read-after-write succeeded;
- writer identity is verified;
- future reuse is durably rejected;
- consumption happened before authorization expiry.

Only then may the external attestation become:

`AUTHORIZATION_CONSUMPTION_ATTESTED`

The contract itself still reports:

`authorization_consumed_by_this_module=false`

## Consumption freshness

The final adapter boundary requires the consumption proof itself to be fresh.

Maximum age:

`15 seconds`

A stale consumption attestation cannot be used to start a future repository
mutation attempt.

## Logical mutation mapping

Only three logical operations exist:

- `PR_DRAFT_TO_READY -> SET_PR_READY_FOR_REVIEW`
- `PR_RETARGET_TO_MAIN -> SET_PR_BASE_TO_MAIN`
- `SQUASH_MERGE_TO_MAIN -> SQUASH_MERGE_PR_TO_MAIN`

These are logical operation identifiers only.

This V1 does not include:

- API endpoint;
- HTTP method;
- GraphQL mutation;
- credential/token;
- raw request payload.

## Adapter boundary

The future trusted adapter must prove:

- signed adapter manifest;
- signed adapter build;
- exact repository identity;
- least-privilege scope;
- exact PR match;
- exact mutation match;
- exact main SHA match;
- exact head SHA match;
- exact base match;
- exact file-delta match;
- exact workflow-snapshot match.

Only then may the boundary reach:

`READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT`

## Single-attempt rule

A positive executor boundary allows at most one future attempt.

It explicitly forbids switching:

- repository;
- PR;
- mutation;
- main SHA;
- head SHA;
- base;
- scope.

Authorization has already been atomically consumed before this point.

A failed or ambiguous future mutation may not simply reuse the receipt.

A future outcome/reconciliation contract is required.

## Explicitly absent

This V1 does not:

- generate a GitHub API request;
- choose API method/endpoint;
- expose credentials;
- open network;
- call GitHub;
- mark a PR Ready;
- retarget/rebase;
- merge;
- close a PR;
- delete a branch;
- deploy;
- activate Worker/provider/production persistence.

## Positive boundary is still not execution

Even at:

`READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT`

the record reports:

- api_request_generated=false
- api_method_selected=false
- api_endpoint_included=false
- credential_material_included=false
- github_api_called=false
- network_called=false
- repository_mutation_performed=false
- merge_executed=false
- retarget_executed=false
- draft_transition_executed=false
- branch_deleted=false
- deploy_executed=false
- worker_activated=false
- provider_activated=false
- production_persistence_activated=false
- executes_action=false

## Next future boundary

The next architectural layer, if ever implemented, must be a real signed GitHub
mutation adapter plus an immutable mutation outcome receipt.

That future layer must distinguish:

- CONFIRMED_SUCCESS;
- CONFIRMED_TERMINAL_FAILURE;
- OUTCOME_UNKNOWN.

Timeout or ambiguous GitHub response must never become inferred success and must
never cause automatic retry.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_REPOSITORY_MUTATION_EXECUTOR_BOUNDARY_V1_CONTRACT_VALIDATED`

No repository mutation is implied.
