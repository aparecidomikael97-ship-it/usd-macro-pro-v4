# AION Owner Stack Live Merge Step Preflight + HUMAN_OWNER Challenge V1

Status: IMPLEMENTATION SAFE / NON-MUTATING  
Date: 2026-10-08  
Scope: future live merge ceremony for #1015 -> #1029  
Repository mutation: NO  
Authorization granted: NO

## Objective

Prepare the exact live preflight and HUMAN_OWNER authorization challenge that
must exist before each future repository mutation.

This V1 separates three mutation classes:

1. `PR_DRAFT_TO_READY`
2. `PR_RETARGET_TO_MAIN`
3. `SQUASH_MERGE_TO_MAIN`

Each mutation requires a new challenge.

Authorization cannot be reused across:

- different mutation types;
- different PRs;
- changed main SHA/tree;
- changed PR HEAD;
- changed file delta;
- changed gate snapshot;
- changed readiness state;
- changed rollback plan;
- expired challenge windows.

## Live preflight

Immediately before a future mutation, the preflight must bind the live:

- PR number;
- requested mutation;
- main SHA;
- main tree SHA;
- PR open state;
- Draft state;
- mergeability;
- base branch;
- head branch;
- head SHA;
- exact four-file delta;
- required workflow results;
- parent-confirmation status;
- current readiness digest;
- rollback-plan digest.

Any drift blocks.

## Root PR #1015

For `PR_DRAFT_TO_READY`:

- #1015 must still be Draft;
- base must be main;
- exact pinned head SHA must still match;
- exact four-file delta must match;
- all five required current-head gates must remain green.

For `SQUASH_MERGE_TO_MAIN`:

- PR must already be out of Draft through a separately authorized step;
- base must still be main;
- all live state must be rebuilt and revalidated.

## Child PRs #1016 onward

Before `PR_RETARGET_TO_MAIN`:

- parent must already be confirmed in main;
- child must already be out of Draft through a separate authorization;
- child must still be based on its expected parent branch;
- exact head/file/gate state must match.

After a real future retarget, old readiness does not carry forward.

A fresh preflight is required for `SQUASH_MERGE_TO_MAIN` with:

- base=main;
- parent confirmed;
- exact head;
- exact four-file delta;
- all required gates green on the current topology.

## Owner challenge

A READY preflight may create:

`OWNER_AUTHORIZATION_CHALLENGE_READY`

The challenge binds:

- challenge ID;
- purpose;
- owner subject;
- owner-binding digest;
- fresh nonce digest;
- exact PR number;
- exact mutation;
- preflight digest;
- main SHA/tree;
- head branch/SHA;
- base branch;
- file-delta digest;
- workflow-snapshot digest;
- readiness digest;
- rollback-plan digest;
- exact confirmation text;
- issue/expiry timestamps.

Maximum window:

`120 seconds`

## Confirmation text

The challenge produces exact human-readable material such as:

`AUTHORIZE PR_DRAFT_TO_READY PR #1015 HEAD <sha> ON MAIN <sha>`

This is challenge material only.

Typing a similar sentence in generic chat is not cryptographic authorization.

## Generic chat is never signature

The contract explicitly states:

- generic_chat_is_authorization=false
- chat_acknowledgement_accepted_as_signature=false
- challenge_is_authorization=false
- real_owner_signature_verified=false
- authorization_granted=false

A future trusted verifier must independently verify the HUMAN_OWNER signature,
trust root, nonce/replay state and exact rebuilt live state.

## Tamper detection

The challenge has a deterministic canonical digest.

Changing any bound field after challenge creation, including the HEAD SHA,
invalidates the challenge digest.

## Expiry

Expired challenges are invalid.

A challenge from the future is invalid.

A challenge window longer than 120 seconds is blocked at construction time.

## State rebuild at execution time

Even a future valid signature cannot be applied blindly.

Immediately before any repository mutation, the executor must rebuild the live
state and require exact equality with the challenge bindings.

This V1 only records that requirement.

It does not implement the executor.

## No authorization reuse

Changing from:

`PR_DRAFT_TO_READY`

to:

`SQUASH_MERGE_TO_MAIN`

requires:

- new live preflight;
- new challenge ID;
- new nonce;
- new owner signature;
- new single-use authorization.

The same applies to retarget vs merge and one PR vs another.

## Branch deletion

Branch deletion is deliberately not one of the supported mutations.

Cleanup remains a separate future ceremony after dependent PR topology is safe.

## Explicit authority boundary

Even a READY challenge reports:

- challenge_is_authorization=false
- real_owner_signature_verified=false
- authorization_granted=false
- repository_mutation_authorized=false
- repository_mutation_performed=false
- merge_executed=false
- retarget_executed=false
- draft_transition_executed=false
- deploy_executed=false
- worker_activated=false
- provider_activated=false
- executes_action=false

## Relationship to the dry-run

The dry-run rehearses ceremony logic.

This V1 prepares the exact live challenge boundary.

Neither can replace live GitHub verification or HUMAN_OWNER cryptographic
authorization.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_OWNER_STACK_LIVE_MERGE_STEP_PREFLIGHT_CHALLENGE_V1_CONTRACT_VALIDATED`

No repository mutation or owner authorization is implied.
