# AION Owner Stack Post-Merge Main Certification + Branch Cleanup Plan V1

Status: IMPLEMENTATION SAFE / NON-MUTATING  
Date: 2026-10-08  
Scope: product stack #1015 -> #1029  
Repository mutation: NO  
Branch deletion authorized: NO

## Objective

Define how to close the future product-stack merge sequence after #1029 reaches
main, and how to clean obsolete product branches without breaking open PR
dependencies or losing evidence.

This block does not merge or delete anything.

## Product stack vs governance stack

The product-stack certification covers exactly:

`#1015 -> #1029`

Those 15 PRs contain 60 intended files total:

- 15 modules;
- 15 test files;
- 15 documentation files;
- 15 dedicated workflows.

Governance PRs #1030+ are separate.

They are not automatically part of the product-stack post-merge certificate and
require their own disposition.

## Post-merge main certification

After the real #1015-#1029 sequence completes, certification requires:

- live main SHA;
- live main tree SHA;
- exact merged PR order #1015 through #1029;
- exact 60-file owner-stack inventory;
- merge-journal digest;
- rollback-plan digest;
- full-stack certification digest;
- full Owner Stack Integration Certification executed on main;
- all 15 product PRs confirmed in main;
- frozen Core integrity verified;
- no unresolved merge conflicts;
- no unexpected main drift.

## Mandatory post-merge gates

All must be green on the final main topology:

- AION Owner Stack Integration Certification V1
- Quality tests
- AtlasQuant - Release Readiness
- AION Core Certification
- AION Core Security Gate

A missing, pending or failed gate blocks closure.

## No activation side effects

Throughout the merge sequence, all must remain false:

- deploy;
- Worker activation;
- provider activation;
- production persistence activation.

If any activation occurred, the product stack cannot be declared cleanly closed
under this contract.

## Positive state

Only after all requirements pass may the result be:

`POST_MERGE_MAIN_CERTIFIED`

Even then:

- branch deletion is not authorized;
- deploy is not authorized;
- Worker/provider activation is not authorized.

The certificate only allows branch-cleanup eligibility to be evaluated.

## Branch evidence preservation

Before a product branch can even become a cleanup candidate, preserve:

- evidence that its intended content is in main;
- branch/head evidence;
- PR metadata;
- workflow evidence;
- deterministic evidence-manifest digest.

Branch deletion must never be the only place where merge evidence exists.

## Open PR dependency hard-stop

A branch cannot be deleted while any open PR uses it as base.

This is especially important for the current governance stack.

Today the topology includes:

- #1030 based on the #1029 product branch;
- #1031 based on #1030;
- #1032 based on #1031;
- #1033 based on #1032;
- this V1 branch based on #1033.

Therefore, even after a future product merge completes, the #1029 product branch
must remain until #1030 is safely retargeted, merged, closed or otherwise given
a separate disposition.

The cleanup planner records such a branch as:

`BLOCKED / OPEN_PR_DEPENDENCY_PRESENT`

## Additional cleanup blockers

A product branch also remains blocked if:

- merge-to-main evidence is missing;
- head evidence was not preserved;
- PR metadata was not preserved;
- workflow evidence was not preserved;
- evidence-manifest digest is missing;
- unmerged commit count is nonzero;
- branch is protected;
- branch is the default branch.

## Cleanup order

The preferred review order is child-before-parent:

`#1029 branch -> #1028 branch -> ... -> #1015 branch`

This minimizes the chance of deleting a parent while a dependent child still
exists.

Eligibility does not imply deletion authority.

## Governance branches

The following governance branches are explicitly excluded from automatic product
cleanup:

- pre-merge readiness;
- rollback/recovery;
- merge ceremony dry-run;
- live merge-step preflight/challenge;
- post-merge certification/cleanup.

They require a separate governance disposition decision.

## Per-branch result

A safe branch may reach:

`ELIGIBLE_FOR_OWNER_CLEANUP_REVIEW`

That still means:

- separate HUMAN_OWNER authorization required;
- branch_deletion_authorized=false;
- branch_deleted=false;
- repository_mutation_performed=false.

## Cleanup candidate verification

A candidate verifier rechecks:

- cleanup plan state;
- target branch is part of product cleanup;
- no cleanup blockers remain;
- no open PR dependency remains;
- deletion is not already preauthorized;
- branch is not already marked deleted.

Maximum candidate state:

`CLEANUP_CANDIDATE_VALID`

This is still review-only.

## Final product-stack closure

The product merge sequence is considered technically closed only when:

1. all #1015-#1029 merges are verified;
2. final main state is certified;
3. all required gates are green;
4. Core integrity remains intact;
5. no activation side effect occurred;
6. branch cleanup is evaluated separately;
7. branch cleanup never destroys open-PR dependency topology.

## Explicit authority boundary

Even a successful certificate/cleanup plan reports:

- branch_deletion_authorized=false
- branch_deleted=false
- deploy_authorized=false
- worker_activation_authorized=false
- provider_activation_authorized=false
- production_persistence_activation_authorized=false
- repository_mutation_performed=false
- external_action_executed=false
- executes_action=false

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_OWNER_STACK_POST_MERGE_CERTIFICATION_CLEANUP_V1_CONTRACT_VALIDATED`

No merge or branch deletion is implied.
