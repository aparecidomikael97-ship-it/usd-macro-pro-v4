# AION B2B Pilot Activation Preflight V1

Status: **staging / ceremony eligibility only / no activation**.

## Objective

Determine whether a previously approved B2B pilot is eligible to enter a future
owner activation ceremony.

`READY_FOR_ACTIVATION_CEREMONY` means only that all preconditions are currently
consistent. It does not issue an activation request and does not authorize or
activate the pilot.

## Required proof chain

The preflight requires all of the following:

### 1. Decision persistence attestation

- exact state `DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE`;
- decision `APPROVE_PILOT`;
- trusted owner / tenant / workspace match;
- owner decision recorded;
- decision record persisted;
- persistence attested;
- receipt consistency verified;
- pilot approved and not denied;
- activation-ceremony eligibility true;
- activation still unauthorized and inactive;
- all external-action flags false.

A persisted DENY blocks immediately.

### 2. Checkpoint writer authority attestation

- exact state `CHECKPOINT_WRITER_AUTHORITY_ATTESTED`;
- writer identity verified;
- writer authority verified;
- exact receipt binding verified;
- anti-replay nonce registered;
- exact same pilot ID;
- exact same receipt digest;
- exact same after-checkpoint digest;
- exact same decision-record digest;
- activation/external-action flags remain false.

### 3. Immutable Owner Review Packet

The original packet remains evidence and must still bind:

- trusted scope;
- candidate ID;
- proposal ID;
- pilot ID;
- packet digest;
- operating-contract digest.

The packet is not mutated into an approval record.

### 4. Pilot Planning Handoff + Operating Contract

The original handoff must remain:

- `PLANNED_FOR_OWNER_REVIEW`;
- `BLOCKED_UNTIL_OWNER_APPROVAL`;
- same candidate / proposal / pilot;
- same trusted scope;
- automatic activation false;
- executes_action false.

The nested Pilot Operating Contract must remain the exact previously reviewed
contract and retain its original activation boundary.

### 5. Fresh activation-environment evidence

The environment must be `VERIFIED`, scoped to the same pilot, and checked no
more than 300 seconds before preflight evaluation.

All must be true:

- tenant isolation ready;
- secrets vault ready;
- rollback ready;
- monitoring ready;
- audit receipts ready;
- sandbox validation passed;
- integration health ready;
- kill switch ready.

All incident flags must be false:

- security incident;
- privacy incident;
- scope breach.

Reserved capacity must fit within available capacity.

Planned monthly infrastructure must respect both:

- the pilot contract budget; and
- the global R$200 B2B infrastructure cap.

At least four environment evidence references are required.

## Successful result

A clean evaluation produces:

`READY_FOR_ACTIVATION_CEREMONY`

and only:

`activation_ceremony_eligible=true`

It still keeps:

- activation_request_issued=false;
- owner_activation_signature_required=true;
- owner_activation_signature_verified=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- customer_contact_authorized=false;
- contract_signature_authorized=false;
- billing_authorized=false;
- spend_authorized=false;
- provisioning_authorized=false;
- deploy_authorized=false;
- crm_write_authorized=false;
- provider_called=false;
- production_mutation_authorized=false;
- executes_action=false.

## Safety boundary

The preflight never:

- treats chat text as activation approval;
- creates or captures an activation signature;
- activates the pilot;
- provisions resources;
- contacts the customer;
- signs a contract;
- bills or spends;
- writes CRM data;
- deploys;
- calls providers;
- mutates production.
