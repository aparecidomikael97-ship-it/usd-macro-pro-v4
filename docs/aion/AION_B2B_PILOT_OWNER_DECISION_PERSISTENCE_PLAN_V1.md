# AION B2B Pilot Owner Decision Persistence Plan V1

Status: **staging / patch candidate only / no checkpoint write**.

## Objective

Prepare a deterministic Checkpoint Master patch candidate from a
cryptographically verified B2B pilot owner decision.

This module exists between decision verification and any future explicit
persistence operation.

## Accepted inputs

The source must be a verified pilot owner decision in exactly one of:

- `OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE`;
- `OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE`.

The decision must still have:

- owner_decision_verified=true;
- owner_decision_recorded=false;
- decision_record_persisted=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- all external-authority flags false.

## Decision record integrity

The plan verifies:

- canonical decision is APPROVE_PILOT or DENY_PILOT;
- approve/deny booleans match the choice;
- decision_record schema and choice match the envelope;
- decision record has not been recorded or persisted;
- decision record still forbids activation;
- decision_record_digest exactly matches the record;
- owner / tenant / workspace / candidate / proposal / pilot IDs are present;
- packet digest and decision-request digest are present.

Tampering fails closed.

## Checkpoint binding

The current Checkpoint Master is reconstructed before the patch candidate is
prepared.

The result binds:

- current expected revision;
- deterministic event ID;
- namespace `aion_b2b_pilot_owner_decision`;
- deterministic patch digest.

The patch candidate is suitable for a later explicit save path, but this module
does not call `append_checkpoint_patch`.

## APPROVE semantics

Even an APPROVE patch candidate keeps:

- owner_decision_recorded=false;
- decision_record_persisted=false;
- checkpoint_saved=false;
- pilot_activation_authorized=false;
- pilot_activated=false.

It may preserve the informational fact that an activation ceremony could become
eligible only **after** persistence and persistence attestation.

## DENY semantics

A DENY patch candidate remains permanently activation-ineligible.

## Required next boundary

A later persistence layer must separately:

1. receive explicit authority to save;
2. compare the expected Checkpoint Master revision;
3. append the exact patch;
4. produce a durable receipt;
5. attest that the exact decision record was persisted.

None of those actions occur in this module.

## Safety boundary

The persistence plan never:

- writes the Checkpoint Master;
- marks a decision persisted;
- authorizes or activates a pilot;
- contacts a customer;
- signs a contract;
- bills or spends;
- writes CRM data;
- deploys;
- calls providers;
- mutates production.
