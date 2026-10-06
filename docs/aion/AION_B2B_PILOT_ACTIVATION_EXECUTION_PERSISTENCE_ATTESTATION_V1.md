# AION B2B Pilot Activation Execution Record Persistence Attestation V1

Status: **staging / verification only / no command generation / no execution**.

## Objective

Verify that the exact signed activation-execution authorization/denial record
was persisted into Checkpoint Master by an external authorized path.

The module never performs the write.

## Required inputs

- Execution Persistence Plan;
- Checkpoint Master before the write;
- externally observed Checkpoint Master after the write;
- execution-specific checkpoint consistency receipt;
- current timestamp.

## Exact persistence checks

The verifier compares the observed state against an in-memory expected
`append_checkpoint_patch(...)` result and validates:

- expected revision;
- deterministic event ID;
- namespace `aion_b2b_pilot_activation_execution_authorization`;
- exact patch and patch digest;
- exact execution record;
- final reconstructed snapshot;
- final journal event;
- before/after checkpoint digests;
- execution-record digest continuity;
- receipt freshness (maximum 180 seconds).

## AUTHORIZE semantics

An exact persisted authorization may produce:

`EXECUTION_RECORD_PERSISTENCE_ATTESTED_AUTHORIZE`

with:

- execution_record_persisted=true;
- persistence_attested=true;
- receipt_consistency_verified=true;
- eligible_for_activation_command_planning=true.

It still keeps:

- writer_identity_verified=false;
- activation_command_generated=false;
- activation_command_executed=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- provisioning_authorized=false;
- deploy_authorized=false;
- executes_action=false.

Eligibility is not a command and is not execution.

## DENY semantics

`EXECUTION_RECORD_PERSISTENCE_ATTESTED_DENY` remains command-planning ineligible.

## Writer boundary

This V1 checks receipt consistency only and rejects a receipt that claims its
writer identity is already verified. A separate cryptographic writer layer is
required.

## Safety boundary

The verifier never writes Checkpoint Master, verifies writer identity,
generates a command, executes activation, provisions, bills, deploys, contacts
a customer or mutates production.
