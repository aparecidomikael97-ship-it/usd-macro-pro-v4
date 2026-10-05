# AION B2B Pilot Activation Execution Ceremony V1

Status: **staging / owner execution signature / no activation command**.

## Objective

Verify an explicit HUMAN_OWNER decision after a clean
`READY_FOR_ACTIVATION_EXECUTION_CEREMONY` preflight.

Accepted decisions are exactly:

- `AUTHORIZE_ACTIVATION_EXECUTION`;
- `DENY_ACTIVATION_EXECUTION`.

Free text, `ok`, booleans, `activate`, `execute`, `authorize` or `vamos lá` are
not converted into execution authorization.

## Signed request

The external Ed25519 signature binds:

- exact execution decision;
- owner / tenant / workspace;
- candidate / proposal / pilot identity;
- execution-environment digest;
- execution-preflight digest;
- ceremony ID;
- nonce;
- issued/expires timestamps;
- owner key ID/version/fingerprint;
- all command/execution/activation flags frozen at false.

## Freshness and anti-replay

The request window is at most 120 seconds.

A durable nonce claim binds pilot, execution-preflight digest, request digest
and owner key version.

Replay fails closed.

## AUTHORIZE semantics

A valid signature produces only:

`ACTIVATION_EXECUTION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE`

It verifies human execution intent but keeps:

- execution_record_persisted=false;
- activation_command_generated=false;
- activation_command_executed=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- provisioning_authorized=false;
- deploy_authorized=false;
- executes_action=false.

A separate persistence/attestation layer is required before command planning.

## DENY semantics

A valid denial produces:

`ACTIVATION_EXECUTION_DENIAL_VERIFIED_PENDING_PERSISTENCE`

and is not command-planning eligible.

## Safety boundary

This module never captures a private key, persists a record, generates an
activation command, executes activation, provisions, bills, deploys, contacts
a customer or mutates production.
