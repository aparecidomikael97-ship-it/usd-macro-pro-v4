# AION Owner Stack Merge Rollback + Recovery V1

Status: IMPLEMENTATION SAFE / REVIEW ONLY  
Date: 2026-10-08  
Scope: future merge sequence for #1015 -> #1029  
Repository mutation: NO  
Rollback authorized: NO

## Objective

Define the rollback and recovery protocol before any merge sequence starts.

The initial repository anchor is:

- main commit: `5744b2b7b17c84331e6f27c569064993ff587782`
- main tree: `c98cc45a56224b187d366079b87a2569f6a357f0`

The tree is the recovery reference because a correct sequence of Git revert
commits preserves history and therefore produces a new commit SHA, even when
the repository contents return to the original state.

## Core rule

Rollback must preserve Git history.

Forbidden:

- force push to main;
- remote reset of main;
- history rewrite;
- automatic revert;
- automatic branch deletion;
- automatic deploy rollback;
- automatic production-data rollback.

The supported recovery mechanism is:

`REVERT_COMMITS_IN_REVERSE_DEPENDENCY_ORDER`

## Why reverse dependency order matters

The owner stack is linear.

If #1016 is found defective after #1017 and #1018 are already merged, reverting
#1016 first could leave children importing or depending on code that no longer
exists.

The safe rollback order is therefore:

`#1018 -> #1017 -> #1016`

The failed parent is reverted only after all merged descendants above it are
removed.

## Evidence captured for every future merge

Before and after each authorized merge step, the merge journal must record:

- PR number;
- pre-merge main SHA;
- pre-merge tree SHA;
- post-merge main SHA;
- post-merge tree SHA;
- actual merge/squash commit SHA;
- exact file delta verification;
- required gate results;
- owner authorization reference;
- deploy=false;
- Worker=false;
- provider activation=false.

A broken SHA chain means unrelated or unexpected main drift and blocks
automatic continuation.

## Unrelated main drift

If main changes outside the expected sequence after the merge process starts:

- stop;
- do not automatically revert;
- do not force main back to the original SHA;
- classify the new changes;
- require human reconciliation.

This prevents rollback logic from deleting unrelated legitimate work.

## Revert conflicts

If a Git revert conflicts:

- stop the rollback sequence;
- preserve the conflict evidence;
- do not auto-resolve;
- do not reset main;
- require human reconciliation and new validation.

## Recovery verification

A full rollback of the entire #1015-#1029 product stack is considered content
recovery only when:

- the resulting main tree SHA equals
  `c98cc45a56224b187d366079b87a2569f6a357f0`;
- all revert commits are verified;
- no unresolved revert conflict exists;
- Quality gates are green;
- the full-stack gate is green when applicable;
- deploy remained false;
- Worker remained false;
- provider activation remained false.

The resulting main commit SHA is expected to differ from the original anchor
because history has been preserved.

## Partial rollback

A partial rollback does not need to restore the original full-stack anchor tree.

Instead it must remove the failed PR and every already-merged descendant, in
reverse dependency order, then reconstruct a fresh pre-merge/readiness snapshot
from the resulting main.

No readiness result survives a rollback unchanged.

## Production scope

The current owner stack PR line is non-deployed and non-activating.

Therefore this rollback contract does not claim production data rollback,
provider compensation, customer-message reversal, contract-signature reversal,
Worker shutdown or infrastructure rollback.

Those would be separate operational domains if they ever become active.

## Authority boundary

Maximum state:

`READY_FOR_HUMAN_OWNER_ROLLBACK_PLAN_REVIEW`

Even a positive plan reports:

- merge_authorized=false
- rollback_authorized=false
- revert_authorized=false
- deploy_authorized=false
- worker_activation_authorized=false
- external_action_authorized=false
- repository_mutation_performed=false
- executes_action=false

## Relationship to pre-merge readiness

This contract consumes the safe state from Owner Stack Pre-Merge Readiness V1.

The merge sequence is not considered ready for real owner authorization unless
both exist:

1. pre-merge readiness;
2. rollback/recovery plan.

Neither contract performs or authorizes repository mutation.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_OWNER_STACK_MERGE_ROLLBACK_RECOVERY_V1_CONTRACT_VALIDATED`
