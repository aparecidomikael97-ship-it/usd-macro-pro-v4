# AION Owner Stack Pre-Merge Readiness V1

Status: IMPLEMENTATION SAFE / REVIEW ONLY  
Date: 2026-10-08  
Scope: stacked PRs #1015 through #1029  
Pinned main: `5744b2b7b17c84331e6f27c569064993ff587782`  
Merge authorized: NO  
Deploy authorized: NO  
Worker activation authorized: NO

## Objective

Prepare a fail-closed merge protocol for the 15 owner-facing PRs already built
and validated.

This block does not merge anything.

It creates an exact pinned snapshot of:

- current main SHA;
- PR order;
- base branch for every PR;
- head branch for every PR;
- exact head SHA for every PR;
- exact four-file delta for every PR;
- required green workflow names.

If any of those values change, the readiness snapshot is invalid.

## Current audited stack

| Order | PR | Base | Head SHA | Required gate |
|---:|---:|---|---|---|
| 1 | #1015 | main | e14f01b03b072c4bc20694e488c1c399ab8c97d1 | AION Owner Experience V1 + Quality + Release Readiness + Core Certification + Core Security Gate |
| 2 | #1016 | #1015 branch | 9f5bdcd10f40917400a28c205efa41dcb86df90d | AION Cognitive Memory Continuity V1 |
| 3 | #1017 | #1016 branch | 02bc4f3550ba40a205d93a0cac43e7fe4358e1ea | AION Secure Local Agent V1 |
| 4 | #1018 | #1017 branch | ca165bac3928bdd0be61b9ff580abdd7ed823d44 | AION Local Action Audit Receipt V1 |
| 5 | #1019 | #1018 branch | 4132ff6e04265a4b44f9b011ec8a9c4f01724073 | AION Secure Desktop Runtime Blueprint V1 |
| 6 | #1020 | #1019 branch | a19f46e6dbf1a3f4e92b9d6439eaf95e58b19543 | AION Voice Hotword Runtime V1 |
| 7 | #1021 | #1020 branch | ef2be130743aba4d9910bb0063cb339dec956009 | AION Teaching Meeting Orchestrator V1 |
| 8 | #1022 | #1021 branch | a46fe0be5f2578821c7f9dbc2ceac2c1fafc5321 | AION Presentation Artifact Control V1 |
| 9 | #1023 | #1022 branch | 13607c00ebdb57156abe3c0ceb806cdf82d93597 | AION Advisor Decision Support V1 |
| 10 | #1024 | #1023 branch | 2994c52d04124aaada8b577dd24fe328c80a2908 | AION Contract Communication Draft Approval V1 |
| 11 | #1025 | #1024 branch | 460932516f9a17fa5baa19bb0f0e6cf7c0963df2 | AION Approval Outbound Dispatch Bridge V1 |
| 12 | #1026 | #1025 branch | f3f3d82205590f7b780ecf30fd29afcd18d703b7 | AION Outbound Execution Authorization Durable Dispatch V1 |
| 13 | #1027 | #1026 branch | 2b3a3de8e0e6d5f48dbd2c2edf3620c7ece660d8 | AION Sealed Provider Outcome Reconciliation V1 |
| 14 | #1028 | #1027 branch | 7187806300d75114da41541fbb7b1928e474ac48 | AION Outbound Terminal Audit Certificate V1 |
| 15 | #1029 | #1028 branch | ad837c2face371526c3c3a29a97e3052e14908b4 | AION Owner Stack Integration Certification V1 |

All 15 PRs were observed:

- open;
- Draft;
- mergeable;
- with the expected base;
- with the expected head SHA;
- with exactly four files each;
- with zero deletions;
- with their required current-head gates green.

## Four-file isolation

Every PR contains only:

1. one AION module;
2. one dedicated test file;
3. one documentation file;
4. one dedicated GitHub Actions workflow.

No PR in #1015-#1029 currently leaks a file into another layer.

That isolation is part of readiness.

If a PR later contains a fifth file or deletion, the snapshot blocks.

## Why the merge cannot be treated as one operation

These are stacked PRs.

The base of #1016 is the branch of #1015, the base of #1017 is #1016, and so on.

After one parent is merged into main, the next child lives in a new repository
topology.

Therefore the old readiness of the child cannot simply be reused.

The sequence must be:

1. verify parent;
2. explicitly authorize parent mutation;
3. merge parent;
4. refetch main;
5. confirm parent is present in main;
6. only then evaluate the child against the new main;
7. retarget/rebase only under explicit authorization;
8. recompute the child diff;
9. require the exact same four-file delta;
10. rerun the child's required gate on its current head/base;
11. stop on any ambiguity;
12. only then ask for/consume authorization for the child step.

## Strict parent-before-child order

The only supported logical order is:

`#1015 -> #1016 -> #1017 -> #1018 -> #1019 -> #1020 -> #1021 -> #1022 -> #1023 -> #1024 -> #1025 -> #1026 -> #1027 -> #1028 -> #1029`

No child may be merged before its parent is confirmed in main.

No step inherits authorization from the prior step.

## Draft handling

Current readiness requires every PR to remain Draft.

Changing Draft -> Ready is itself a repository mutation and requires separate
owner authorization.

Pre-merge readiness is deliberately not permission to change Draft state.

## Retarget/rebase handling

For #1016 onward:

- parent must already be confirmed in main;
- main must be refetched;
- child base change must be explicit;
- the post-retarget/rebase diff must remain exactly the child's four intended files;
- no deletion is allowed;
- the child's required workflow must run again and be green;
- the previous readiness snapshot becomes stale.

The contract does not choose automatically between retarget and rebase.

That choice is deferred until the real sequence because the repository state at
that moment is authoritative.

## Branch deletion

Do not delete a parent branch while an open child still depends on it unless the
child has already been safely retargeted/rebased and revalidated.

Branch cleanup is not part of a merge authorization.

It is a separate operation.

## Squash merge

Squash merge may be used only if the HUMAN_OWNER explicitly authorizes the
specific merge step.

The pre-merge contract does not authorize squash merge.

It only records that a future sequence may use it under explicit authorization
and full revalidation.

## Required stop conditions

Stop the sequence immediately if any of the following occurs:

- main changed unexpectedly;
- target PR HEAD changed;
- target PR base changed outside the planned transition;
- target PR is not mergeable;
- target PR is closed unexpectedly;
- target PR has an extra/missing file;
- target PR introduces a deletion;
- required gate is missing, pending or failed;
- post-retarget diff differs from the pinned four-file delta;
- parent cannot be confirmed in main;
- a child loses compatibility after its parent merge;
- branch topology becomes ambiguous;
- owner authorization is absent or does not exactly cover the requested mutation.

## Final verification after #1029

After the final product-stack PR is eventually merged:

1. refetch main;
2. rerun the full Owner Stack Integration Certification against main;
3. verify all owner-stack modules are present;
4. run a post-merge main audit;
5. prove no deploy/Worker/provider/persistence activation happened as a side effect;
6. only then declare the merge sequence technically closed.

This future post-merge verification is mandatory.

## What readiness means

Maximum state:

`READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW`

It means the current snapshot is coherent enough to present a merge sequence for
human review.

It does not mean:

- ready to merge automatically;
- merge approved;
- retarget approved;
- rebase approved;
- branch deletion approved;
- deploy approved;
- Worker approved;
- provider activation approved;
- production persistence approved.

## Explicit authority boundaries

Even a positive result reports:

- merge_authorized=false
- retarget_authorized=false
- rebase_authorized=false
- deploy_authorized=false
- worker_activation_authorized=false
- provider_activation_authorized=false
- external_action_authorized=false
- merge_executed=false
- deploy_executed=false
- core_checkpoint_write=false
- executes_action=false

## Relationship to #1030

This readiness contract itself is a meta/audit layer stacked above #1029.

It is not included in the 15 product-stack PRs being certified by this pinned
snapshot.

Its eventual disposition must be reviewed separately from the #1015-#1029
product merge sequence.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_OWNER_STACK_PRE_MERGE_READINESS_V1_CONTRACT_VALIDATED`

No repository mutation is implied.
