# AION B2B Pilot Activation Execution Persistence Plan V1

Status: **staging / Checkpoint Master patch candidate only**.

## Objective

Prepare a deterministic Checkpoint Master patch candidate for a verified
activation-execution authorization/denial.

## Accepted source

The source must be cryptographically verified and still pending persistence.

It must preserve:

- execution_record_persisted=false;
- activation_command_generated=false;
- activation_command_executed=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- all external authority flags false;
- exact execution-record digest;
- exact execution-environment / execution-preflight / request digests;
- decision and intent booleans consistent.

## Checkpoint binding

The plan produces:

- namespace `aion_b2b_pilot_activation_execution_authorization`;
- current expected checkpoint revision;
- deterministic event ID;
- exact patch digest;
- explicit-save requirement;
- persistence-attestation requirement.

The module never calls `append_checkpoint_patch`.

## AUTHORIZE semantics

An AUTHORIZE patch candidate may carry informational eligibility for a future
command-planning layer only after persistence and attestation.

It still keeps command generation, execution and pilot activation false.

## DENY semantics

A DENY patch remains command-planning ineligible.

## Safety boundary

The plan never writes Checkpoint Master, claims persistence, generates or
executes an activation command, activates a pilot, provisions, bills, deploys
or mutates production.
