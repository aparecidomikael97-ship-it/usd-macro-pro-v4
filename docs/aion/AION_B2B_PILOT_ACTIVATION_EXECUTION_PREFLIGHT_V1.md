# AION B2B Pilot Activation Execution Preflight V1

Status: **staging / final execution eligibility gate / no command generation**.

## Objective

Determine whether a previously signed and durably persisted pilot activation
authorization may enter a future HUMAN_OWNER activation-execution ceremony.

`READY_FOR_ACTIVATION_EXECUTION_CEREMONY` is only eligibility. It is not an
activation command, activation authority or pilot activation.

## Required proof chain

### 1. Activation authorization persistence

The exact activation record must be:

- state `ACTIVATION_RECORD_PERSISTENCE_ATTESTED_AUTHORIZE`;
- decision `AUTHORIZE_PILOT_ACTIVATION`;
- scope-bound to the trusted owner/tenant/workspace;
- persisted and persistence-attested;
- receipt consistency verified;
- activation intent true and denial false;
- execution-preflight eligible;
- all activation/external-action flags still false.

A persisted activation denial blocks.

### 2. Activation checkpoint writer authority

The second checkpoint write must have:

- state `ACTIVATION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED`;
- writer identity verified;
- writer authority verified;
- receipt binding verified;
- anti-replay nonce registered;
- exact same pilot ID;
- exact same receipt digest;
- exact same after-checkpoint digest;
- exact same activation-record digest;
- no activation/execution authority.

### 3. Original Activation Preflight continuity

The original preflight remains immutable evidence and must preserve:

- exact scope;
- candidate / proposal / pilot IDs;
- original environment digest;
- original preflight digest;
- activation-ceremony eligibility;
- every external-action flag false.

### 4. Fresh execution environment

The execution environment must be `VERIFIED`, scoped to the same pilot and
checked no more than 120 seconds before evaluation.

Execution mode must be exactly `CONTROLLED_PILOT`.

Required true:

- activation slot reserved;
- tenant isolation ready;
- secrets vault ready;
- rollback ready;
- monitoring ready;
- audit receipts ready;
- integration health ready;
- kill switch ready;
- idempotency key ready;
- single-pilot lock ready;
- dry-run validation passed.

Required false:

- production scope expansion allowed;
- security incident;
- privacy incident;
- scope breach;
- provider degraded;
- rollback degraded.

Reserved capacity must fit available capacity.

Planned monthly infrastructure must remain at or below R$200.

At least six execution-environment evidence references are required.

## Successful result

A clean gate produces:

`READY_FOR_ACTIVATION_EXECUTION_CEREMONY`

with only:

`activation_execution_ceremony_eligible=true`

and keeps:

- human_execution_confirmation_required=true;
- execution_request_issued=false;
- owner_execution_signature_verified=false;
- activation_command_generated=false;
- activation_command_executed=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- customer_contact_authorized=false;
- billing_authorized=false;
- provisioning_authorized=false;
- deploy_authorized=false;
- crm_write_authorized=false;
- provider_called=false;
- production_mutation_authorized=false;
- executes_action=false.

## Safety boundary

The preflight never creates an execution request, captures a signature,
generates an activation command, activates a pilot, provisions resources,
contacts a customer, bills, deploys, writes CRM data or mutates production.
