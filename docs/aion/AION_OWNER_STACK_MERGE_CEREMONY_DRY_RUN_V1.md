# AION Owner Stack Merge Ceremony Dry-Run V1

Status: IMPLEMENTATION SAFE / SYNTHETIC SIMULATION ONLY  
Date: 2026-10-08  
Scope: future merge sequence #1015 -> #1029  
Repository mutation: NO  
Merge authorized: NO  
Retarget/rebase authorized: NO  
Rollback authorized: NO

## Objective

Rehearse the complete future merge ceremony without touching GitHub state.

The dry-run consumes:

1. Owner Stack Pre-Merge Readiness V1;
2. Merge Sequence Plan V1;
3. Merge Rollback + Recovery V1.

It then simulates the 15 product-stack merge steps.

No branch is retargeted.
No PR is moved out of Draft.
No merge commit is created.
No revert is executed.

## Virtual SHAs

The dry-run produces deterministic 40-hex identifiers for:

- virtual post-merge main;
- virtual post-merge tree;
- virtual revert commits;
- virtual partial-recovery tree.

These values look like Git SHAs only to make continuity testing convenient.

They are explicitly **not Git objects** and are never written to the repository.

## Happy-path ceremony

The simulated path is:

`#1015 -> #1016 -> ... -> #1029`

For #1015:

- validate parent-free root step;
- simulate explicit owner authorization;
- verify exact four-file delta;
- verify required gates;
- simulate merge into main;
- advance virtual main/tree.

For every child #1016 onward:

1. confirm parent is in the virtual main;
2. simulate fresh owner authorization;
3. simulate Draft transition;
4. simulate retarget to main;
5. invalidate old readiness;
6. recompute exact four-file delta;
7. simulate gate rerun;
8. require green result;
9. simulate child merge;
10. advance virtual main/tree.

At every step:

- deploy remains false;
- Worker remains false;
- provider activation remains false;
- no repository mutation occurs.

## Stop conditions rehearsed

The simulator supports deliberate fault injection for:

- MAIN_DRIFT
- HEAD_DRIFT
- BASE_DRIFT
- FILE_DELTA_DRIFT
- DELETION_DETECTED
- GATE_FAILURE
- OWNER_AUTHORIZATION_MISSING
- DRAFT_TRANSITION_NOT_AUTHORIZED
- PARENT_NOT_CONFIRMED_IN_MAIN
- RETARGET_CONFLICT
- POST_RETARGET_DIFF_DRIFT
- POST_RETARGET_GATE_FAILURE
- MERGE_CONFLICT
- UNEXPECTED_DEPLOY
- UNEXPECTED_WORKER_ACTIVATION
- UNEXPECTED_PROVIDER_ACTIVATION

Any injected stop condition prevents the simulated merge for that step.

The dry-run state becomes:

`DRY_RUN_STOP_CONDITION_VERIFIED`

This proves that the ceremony fails closed rather than attempting to continue.

## Owner authorization in the dry-run

The simulator may mark:

`synthetic_owner_authorization_simulated=true`

This only means the workflow path requiring authorization was exercised.

It is never treated as a real HUMAN_OWNER authorization.

The global result always reports:

`real_owner_authorization_used=false`

## Retarget simulation

For every child PR, the dry-run checks the intended future sequence:

- parent confirmed first;
- retarget simulated to main;
- exact four-file delta retained;
- no deletion;
- dedicated gate rerun simulated;
- old readiness not reused.

It always reports:

- actual_retarget_performed=false
- actual_rebase_performed=false

## Full rollback rehearsal

A full rollback simulation can model all #1015-#1029 as merged and inject a
failure at #1015.

Expected virtual revert order:

`#1029 -> #1028 -> ... -> #1015`

The simulated recovered tree then equals the pinned pre-sequence tree:

`c98cc45a56224b187d366079b87a2569f6a357f0`

No real revert is performed.

## Partial rollback rehearsal

If all 15 PRs are virtually merged and failure is assigned to #1024, the
simulator removes only:

`#1029 -> #1028 -> #1027 -> #1026 -> #1025 -> #1024`

The remaining simulated stack is:

`#1015 -> ... -> #1023`

Therefore the recovery tree is intentionally not equal to the original anchor.

A new real readiness snapshot would be required after any future partial
rollback.

## Noncanonical history

A rollback simulation blocks if merged PR history is not parent-before-child.

For example:

`#1015, #1017, #1016`

is invalid.

The dry-run does not attempt to repair or reinterpret an invalid merge history.

## Positive result

The maximum happy-path state is:

`DRY_RUN_SEQUENCE_COMPLETED`

This means the synthetic ceremony traversed all 15 planned steps.

It does **not** mean:

- any real owner authorization was consumed;
- any PR is ready to be changed automatically;
- retarget was executed;
- rebase was executed;
- merge was executed;
- rollback was executed;
- deploy is allowed;
- Worker is allowed;
- provider activation is allowed.

## Explicit authority boundary

Even a successful dry-run reports:

- synthetic_only=true
- virtual_shas_are_not_git_objects=true
- real_owner_authorization_used=false
- repository_mutation_performed=false
- actual_merge_executed=false
- actual_retarget_executed=false
- actual_rebase_executed=false
- actual_revert_executed=false
- merge_authorized=false
- retarget_authorized=false
- rebase_authorized=false
- revert_authorized=false
- deploy_authorized=false
- executes_action=false

## Relationship to future real merge ceremony

The real sequence must still use live GitHub state at every step.

The dry-run can never replace:

- live main refetch;
- live tree/diff verification;
- live mergeability;
- live current-head gates;
- explicit HUMAN_OWNER authorization;
- live post-merge verification;
- live rollback evidence.

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_OWNER_STACK_MERGE_CEREMONY_DRY_RUN_V1_SYNTHETIC_VALIDATED`
