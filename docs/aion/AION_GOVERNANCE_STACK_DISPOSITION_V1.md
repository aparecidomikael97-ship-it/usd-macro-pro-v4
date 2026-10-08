# AION Governance Stack Disposition V1

Status: IMPLEMENTATION SAFE / NON-MUTATING  
Date: 2026-10-08  
Scope: governance PRs #1030 -> #1034  
Repository mutation: NO  
Governance merge authorized: NO

## Objective

Define the final disposition of the five governance PRs created above the
product stack.

The product stack is:

`#1015 -> #1029`

The governance stack is:

`#1030 -> #1031 -> #1032 -> #1033 -> #1034`

This V1 decides which governance PRs become permanent repository evidence,
which remain active governance references, and whether any current PR can be
safely closed unmerged.

## Decision

Current topology requires all five governance PRs to be preserved and merged in
strict order **after** the product stack is merged and certified.

No current PR in #1030-#1034 is safe to close unmerged.

### Frozen historical governance evidence

#### #1030 — Owner Stack Pre-Merge Readiness V1

Post-merge role:

`FROZEN_HISTORICAL_REFERENCE`

Reason:

- pins the exact pre-merge stack snapshot;
- preserves the exact HEAD/base/gate evidence used before the real ceremony;
- is imported by later governance modules.

After merge it must not be rewritten to pretend that the old pinned state is
still current.

A future readiness V2 may supersede it.

#### #1032 — Merge Ceremony Dry-Run V1

Post-merge role:

`FROZEN_HISTORICAL_REFERENCE`

Reason:

- records the exact synthetic rehearsal used before real mutation;
- proves tested hard-stops and rollback behavior;
- sits in the stacked ancestry below later governance PRs.

It remains historical evidence, not an always-current operational simulator.

### Maintained governance references

#### #1031 — Merge Rollback + Recovery V1

Post-merge role:

`MAINTAINED_GOVERNANCE_REFERENCE`

It remains the current reference for:

- preserving Git history;
- reverse-dependency revert order;
- no force-push/reset recovery;
- merge journal requirements;
- tree-level recovery verification.

A future V2 may supersede it without deleting V1 evidence.

#### #1033 — Live Merge Step Preflight + Owner Challenge V1

Post-merge role:

`MAINTAINED_GOVERNANCE_REFERENCE`

It remains the reference for:

- live mutation preflight;
- exact state binding;
- separate Draft/retarget/merge ceremonies;
- HUMAN_OWNER challenge boundaries;
- no generic-chat-as-signature;
- no authorization reuse.

#### #1034 — Post-Merge Main Certification + Branch Cleanup V1

Post-merge role:

`MAINTAINED_GOVERNANCE_REFERENCE`

It remains the reference for:

- product-stack closure on main;
- final gate requirements;
- frozen Core integrity;
- branch-cleanup eligibility;
- dependency-aware branch deletion;
- evidence preservation before cleanup.

## Why none should be skipped

The current governance PR stack is not five independent documents.

Technical dependencies exist:

- later modules import #1030;
- #1032 lies in the ancestry path before #1033;
- #1034 is stacked on #1033;
- skipping a middle PR changes the effective diff of later stacked PRs.

Therefore this V1 requires:

`#1030 -> #1031 -> #1032 -> #1033 -> #1034`

No middle PR may be silently skipped.

## Why not close #1030/#1032 as unmerged evidence

They are historical in meaning, but not disposable in the current topology.

Closing them unmerged while keeping later PRs would require one of:

- rebasing/cherry-picking later PRs around them;
- copying dependencies elsewhere;
- producing a consolidated governance V2;
- rebuilding and revalidating the stack.

That would be a new design and new risk surface.

Therefore the current safe decision is:

- merge them;
- preserve them;
- mark their role as historical;
- never pretend they are current live state.

## Product stack must close first

Governance disposition cannot begin merely because the governance PRs are green.

Before #1030 can enter a future real merge ceremony, require:

- product stack #1015-#1029 confirmed in main;
- product post-merge certification;
- full owner-stack gate green on main;
- frozen Core integrity verified;
- deploy remained disabled;
- Worker remained disabled;
- provider activation remained disabled;
- production persistence remained disabled.

Only then may governance disposition reach:

`READY_FOR_HUMAN_OWNER_GOVERNANCE_DISPOSITION_REVIEW`

## Governance merge order

Strict order:

1. #1030
2. #1031
3. #1032
4. #1033
5. #1034

Every step requires:

- live main refetch;
- parent confirmed in main;
- separate HUMAN_OWNER authorization;
- separate Draft -> Ready authorization;
- separate retarget/rebase authorization where needed;
- separate merge authorization;
- exact four-file delta after base change;
- zero deletions;
- dedicated gate rerun;
- stop on any drift or ambiguity.

No authorization carries from one mutation to the next.

## Retention rules after merge

### Historical V1 files

For #1030 and #1032:

- remain in main;
- preserve PR metadata;
- preserve workflow evidence;
- preserve HEAD/merge evidence;
- do not rewrite old pinned facts as if they were current;
- future V2 should supersede rather than erase.

### Active reference V1 files

For #1031, #1033 and #1034:

- remain in main as current governance references until superseded;
- future improvements should use a new version/PR;
- V1 evidence remains preserved.

## Branch cleanup

Governance branch cleanup begins only after all five governance PRs are merged
and every dependent PR has been resolved.

Cleanup should be child-before-parent:

`#1034 branch -> #1033 branch -> #1032 branch -> #1031 branch -> #1030 branch`

However, this V1 itself is stacked on #1034.

Therefore #1034's branch cannot be deleted while the disposition PR is still
open and depends on it.

This disposition PR is meta-governance and requires its own later decision.

## Governance consolidation V2

A future consolidated governance design is allowed, but it must be a separate
explicit project.

It may:

- replace stack-specific constants with generalized contracts;
- reduce the number of modules;
- create reusable merge-governance primitives.

It must not retroactively erase or rewrite V1 historical evidence.

Current #1030-#1034 cannot be treated as safely closeable merely because a
future consolidation is planned.

## Explicit authority boundary

Even a positive disposition plan reports:

- governance_merge_authorized=false
- pr_close_authorized=false
- retarget_authorized=false
- rebase_authorized=false
- branch_delete_authorized=false
- deploy_authorized=false
- repository_mutation_performed=false
- executes_action=false

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_GOVERNANCE_STACK_DISPOSITION_V1_CONTRACT_VALIDATED`

No PR transition, merge, close or branch deletion is implied.
