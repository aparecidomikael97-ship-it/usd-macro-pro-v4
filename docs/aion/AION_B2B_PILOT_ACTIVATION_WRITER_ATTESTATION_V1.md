# AION B2B Pilot Activation Checkpoint Writer Attestation V1

Status: **staging / cryptographic writer proof / no activation**.

## Objective

Verify that a trusted external Checkpoint Master writer key acknowledged the
exact receipt for persistence of the signed pilot activation record.

This is the second writer proof in the B2B pilot chain:

- the first writer attests persistence of the owner APPROVE/DENY pilot decision;
- this writer attests persistence of the later activation authorization/denial.

## Exact receipt binding

The signed request binds:

- activation receipt digest;
- storage target `CHECKPOINT_MASTER`;
- namespace `aion_b2b_pilot_activation_authorization`;
- event ID;
- pilot ID;
- after-checkpoint digest;
- activation-record digest;
- writer reference;
- ceremony ID;
- nonce;
- issued/expires timestamps;
- trusted writer key ID/version/fingerprint.

## Cryptographic boundary

The mechanism is Ed25519 over canonical request bytes.

The public key comes from `TrustRootRegistry` and the private key remains
external to AtlasQuant.

## Freshness and replay

The signature request is valid for at most 180 seconds.

A durable `PersistentNonceRegistry` claim protects the exact pilot/receipt/
request/key tuple from replay.

## Successful result

A valid signature produces:

`ACTIVATION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED`

with:

- writer_identity_verified=true;
- writer_authority_verified=true;
- receipt_binding_verified=true;
- nonce_registered=true.

It still keeps:

- pilot_activation_authorized=false;
- pilot_activated=false;
- checkpoint_write_performed=false;
- customer_contact_authorized=false;
- billing_authorized=false;
- provisioning_authorized=false;
- deploy_authorized=false;
- production_mutation_authorized=false;
- executes_action=false.

## Safety boundary

The module never captures a private key, performs the checkpoint write,
activates a pilot, provisions resources, contacts a customer, bills, deploys
or mutates production.
