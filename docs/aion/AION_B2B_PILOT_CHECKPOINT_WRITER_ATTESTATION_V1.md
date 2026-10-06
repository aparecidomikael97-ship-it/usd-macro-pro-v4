# AION B2B Pilot Checkpoint Writer Authority Attestation V1

Status: **staging / cryptographic writer verification / no write / no activation**.

## Objective

Cryptographically verify that an authorized external checkpoint-writer key
acknowledged the exact B2B pilot decision persistence receipt.

This layer complements the separate persistence-content attestation.

Persistence-content attestation proves **what** was persisted.
Writer attestation proves control of an approved writer key over the exact
receipt being acknowledged.

Neither layer performs the write.

## Receipt preconditions

The source receipt must remain:

- schema `ATLASQUANT_AION_B2B_PILOT_DECISION_CHECKPOINT_RECEIPT_V1`;
- status `CONFIRMED`;
- storage target `CHECKPOINT_MASTER`;
- write mode `EXPLICIT_AUTHORIZED_APPEND`;
- namespace `aion_b2b_pilot_owner_decision`;
- event ID present;
- pilot ID present;
- writer reference present;
- patch/before/after/decision-record digests valid;
- receipt digest valid;
- writer_identity_verified=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- external_action_executed=false.

A receipt that arrives claiming its own writer identity is already verified is
rejected. Identity proof belongs to this separate cryptographic layer.

## External writer signature request

The request binds:

- exact receipt digest;
- Checkpoint Master target;
- namespace;
- event ID;
- pilot ID;
- after-checkpoint digest;
- decision-record digest;
- writer reference;
- ceremony ID;
- nonce;
- issued/expires timestamps;
- writer key ID/version/fingerprint;
- activation and external-action flags frozen at false.

The signature mechanism is Ed25519 using a public key from TrustRootRegistry.

Private-key material is never read, stored or produced by this module.

## Anti-replay

The request has a maximum 180-second window.

A durable PersistentNonceRegistry claim binds the nonce to:

- pilot ID;
- receipt digest;
- request digest;
- writer key ID/version.

Replay fails closed.

## Successful result

A valid external signature produces:

`CHECKPOINT_WRITER_AUTHORITY_ATTESTED`

with:

- writer_identity_verified=true;
- writer_authority_verified=true;
- receipt_binding_verified=true;
- nonce_registered=true.

This proves control of the configured trusted writer key over the exact receipt.

It still keeps:

- pilot_activation_authorized=false;
- pilot_activated=false;
- checkpoint_write_performed=false;
- customer_contact_authorized=false;
- billing_authorized=false;
- deploy_authorized=false;
- production_mutation_authorized=false;
- executes_action=false.

## Safety boundary

The module never:

- captures or creates a private writer key;
- writes Checkpoint Master;
- repeats the persistence operation;
- activates the pilot;
- contacts the customer;
- bills or spends;
- changes CRM;
- deploys;
- mutates production.
