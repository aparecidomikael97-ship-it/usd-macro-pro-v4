# AION Repository Mutation Authorization Receipt V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING  
Date: 2026-10-08  
Scope: future repository mutation authorization for the product-stack ceremony  
Repository mutation performed: NO  
Authorization consumed: NO

## Objective

Close the authorization boundary between a valid live merge-step challenge and a
future repository mutation executor.

This V1 preserves the accepted AION rule:

`SIGNATURE != DECISION != EXECUTION`

A valid owner signature is not automatically a decision.

A valid decision is not automatically execution.

A valid authorization receipt is still not execution.

## Sequence

The intended future sequence is:

1. live preflight rebuild;
2. owner authorization challenge;
3. external Ed25519 HUMAN_OWNER signature verification;
4. separate explicit owner mutation decision;
5. live repository state rebuild again;
6. exact state equality with the challenge;
7. single-use authorization receipt;
8. durable receipt persistence attestation;
9. future executor revalidates state again;
10. future executor atomically consumes authorization;
11. only then may exactly one requested repository mutation be attempted.

This V1 implements steps 3-8 as pure contracts.

It does not implement step 10 or 11.

## Owner signature attestation

The signature attestation requires:

- valid fresh challenge;
- exact challenge digest;
- HUMAN_OWNER key fingerprint;
- Ed25519 external owner repository-mutation mechanism;
- active trust root;
- signer subject match;
- owner-binding match;
- persistent challenge-nonce replay guard;
- single-use challenge nonce claim.

A positive state is:

`OWNER_SIGNATURE_ATTESTED`

It explicitly reports:

- signature_is_decision=false
- approval_implied_by_signature=false
- mutation_decision=UNDECIDED
- repository_mutation_authorized=false

## Separate explicit owner decision

After signature attestation, a second signed record must explicitly be one of:

- AUTHORIZE_REPOSITORY_MUTATION
- DENY_REPOSITORY_MUTATION

The decision record binds:

- decision ID;
- purpose;
- exact challenge digest;
- exact signature-attestation digest;
- exact PR;
- exact mutation type;
- owner subject/binding;
- owner key fingerprint;
- fresh decision nonce;
- issue/expiry timestamps.

The decision itself is signed separately.

It requires:

- verified owner decision signature;
- active trust root;
- separate persistent nonce replay guard;
- single-use decision nonce.

The decision window cannot exceed 120 seconds or outlive the challenge.

## DENY is terminal for that receipt attempt

If the explicit decision is:

`DENY_REPOSITORY_MUTATION`

the authorization receipt cannot become positive.

A fresh ceremony would be required for any later attempt.

## Live state rebuild before receipt

Before receipt creation, the live preflight is rebuilt again.

It must match the challenge exactly on:

- PR number;
- mutation;
- main SHA;
- main tree SHA;
- head branch;
- head SHA;
- base branch;
- exact file-delta digest;
- workflow-snapshot digest;
- readiness digest;
- rollback-plan digest;
- preflight digest.

Any drift blocks receipt creation.

This prevents a valid signature from being reused after repository state changes.

## Authorization receipt

A positive receipt state is:

`REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED`

The receipt is scoped to exactly one:

- PR;
- mutation;
- HEAD;
- main SHA/tree;
- base;
- file delta;
- gate snapshot;
- readiness;
- rollback plan.

It reports:

- repository_mutation_authorized=true
- authorized_for_exactly_one_mutation=true
- authorization_single_use=true
- authorization_consumed=false
- repository_mutation_performed=false

The meaning of `repository_mutation_authorized=true` is narrow:

the receipt is a verified authorization artifact for a future executor.

It does not mean GitHub has been changed.

## Authorization reuse forbidden

A receipt cannot be reused for:

- another PR;
- another mutation;
- another HEAD;
- another main SHA/tree;
- another base;
- another file delta;
- another gate snapshot;
- broader scope.

All reuse/expansion flags are false.

## Receipt expiry

The receipt window is bounded to 120 seconds and cannot outlive:

- the original challenge;
- the explicit owner decision.

An expired receipt is invalid.

## Durable receipt persistence

Before any future executor may act, the receipt must be durably persisted by a
separate trusted writer.

The persistence attestation requires:

- exact authorization-receipt digest;
- persisted-record digest;
- writer-attestation digest;
- read-after-write verification;
- atomic write or CAS;
- writer identity verification;
- persistence before receipt expiry.

This module does not write the record itself.

It reports:

`authorization_persisted_by_this_module=false`

## Atomic consumption still required later

Even a persisted authorization receipt remains:

`authorization_consumed=false`

A future executor must atomically consume the authorization at the final
execution boundary.

That future operation is not implemented here.

## Tamper detection

The receipt is deterministic and digest-bound.

Changing a bound field such as:

- HEAD SHA;
- main SHA;
- mutation;
- base;
- file-delta digest;

invalidates receipt verification.

## Generic chat boundary

This contract inherits and strengthens the rule:

- generic chat is not signature;
- generic chat is not decision;
- generic chat is not authorization.

A phrase such as "vamos lá" is not the external Ed25519 ceremony defined here.

## Explicitly absent

This V1 does not:

- mark a PR Ready;
- retarget a PR;
- rebase a PR;
- merge a PR;
- close a PR;
- delete a branch;
- call GitHub mutation APIs;
- deploy;
- activate Worker;
- activate a provider;
- activate production persistence;
- consume a real authorization.

## Positive receipt is not execution

Even a positive authorization receipt reports:

- authorization_consumed=false
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

## Validation target

After dedicated CI is green, the maximum truthful milestone is:

`AION_REPOSITORY_MUTATION_AUTHORIZATION_RECEIPT_V1_CONTRACT_VALIDATED`

No repository mutation is implied.
