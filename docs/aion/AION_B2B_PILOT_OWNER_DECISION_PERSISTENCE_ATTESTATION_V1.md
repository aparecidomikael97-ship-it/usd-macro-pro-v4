# AION B2B Pilot Owner Decision Persistence Attestation V1

Status: **staging / verification only / no storage write**.

## Objective

Verify that the exact cryptographically verified B2B pilot owner-decision record
was persisted into Checkpoint Master by an external authorized persistence path.

This module never performs the write itself.

## Inputs

The verifier requires:

- the previously prepared Pilot Owner Decision Persistence Plan;
- the exact Checkpoint Master before persistence;
- the externally observed Checkpoint Master after persistence;
- an externally supplied checkpoint-write consistency receipt;
- a current timestamp for freshness checks.

## Expected checkpoint simulation

The verifier uses the pure `append_checkpoint_patch(...)` contract only in memory
to compute the exact expected post-write snapshot and journal event.

This is simulation for comparison only:

- storage_write_performed=false;
- network_called=false;
- external_action_executed=false.

## Exact persistence checks

The attestation verifies:

- prior checkpoint integrity;
- expected revision;
- deterministic event ID;
- exact namespace `aion_b2b_pilot_owner_decision`;
- exact patch digest;
- exact decision record;
- observed revision;
- observed reconstructed snapshot;
- observed final journal event;
- proposal/pilot decision record digest continuity.

Any difference fails closed.

## Receipt consistency

The external receipt must bind:

- storage target `CHECKPOINT_MASTER`;
- write mode `EXPLICIT_AUTHORIZED_APPEND`;
- namespace;
- event ID;
- base revision and resulting revision;
- patch digest;
- checkpoint digest before write;
- checkpoint digest after write;
- decision record digest;
- pilot ID;
- persisted timestamp;
- writer reference;
- canonical receipt digest.

The receipt must be no older than 300 seconds at verification time.

## Writer identity boundary

V1 verifies receipt consistency only.

It **does not** cryptographically verify the writer identity, therefore:

`writer_identity_verified=false`

and a receipt that claims `writer_identity_verified=true` is rejected.

A future layer may add a separately verifiable writer identity/authority receipt.

## APPROVE semantics

An exact persisted APPROVE decision may produce:

`DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE`

with:

- owner_decision_recorded=true;
- decision_record_persisted=true;
- persistence_attested=true;
- eligible_for_activation_ceremony=true.

However, it still keeps:

- pilot_activation_authorized=false;
- pilot_activated=false;
- customer_contact_authorized=false;
- contract_signature_authorized=false;
- billing_authorized=false;
- spend_authorized=false;
- deploy_authorized=false;
- crm_write_authorized=false;
- production_mutation_authorized=false.

Eligibility is not authorization.

## DENY semantics

An exact persisted DENY decision produces:

`DECISION_RECORD_PERSISTENCE_ATTESTED_DENY`

and remains ineligible for activation.

## Safety boundary

The attestation never:

- writes Checkpoint Master;
- creates a storage transaction;
- verifies writer identity beyond receipt consistency;
- activates a pilot;
- contacts a customer;
- signs a commercial contract;
- bills or spends;
- writes CRM data;
- deploys;
- calls providers;
- mutates production.
