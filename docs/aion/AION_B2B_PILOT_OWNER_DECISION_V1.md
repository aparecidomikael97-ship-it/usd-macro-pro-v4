# AION B2B Pilot Owner Decision V1

Status: **staging / cryptographic decision verification / no activation**.

## Objective

Create a pilot-specific HUMAN_OWNER decision ceremony that is separate from the
existing Core-Freeze owner-decision mechanism.

Accepted choices are exactly:

- `APPROVE_PILOT`;
- `DENY_PILOT`.

No alias, boolean, free text, `ok`, `approved`, `vamos lá` or generic chat
instruction is converted into a decision.

## Why this is separate from Core Freeze

The existing owner decision path is scoped to:

- `APPROVE_CORE_FREEZE`;
- `DENY_CORE_FREEZE`.

Pilot approval is a different semantic and authority domain. Reusing the
Core-Freeze decision request would risk confusing infrastructure governance with
commercial/customer-operation approval.

## Preconditions

The decision request requires a current Pilot Owner Review Packet with:

- state `READY_FOR_OWNER_REVIEW`;
- owner_decision `UNDECIDED`;
- no recorded owner decision or approval;
- activation still unauthorized;
- all external/action flags false;
- valid trusted owner / tenant / workspace scope;
- candidate ID;
- proposal ID;
- pilot ID;
- packet digest;
- proposal/readiness/handoff/operating-contract digests;
- pilot activation state `BLOCKED_UNTIL_OWNER_APPROVAL`.

## External signature request

The request binds:

- exact canonical decision;
- owner / tenant / workspace;
- candidate ID;
- proposal ID;
- pilot ID;
- exact owner-review packet digest;
- exact proposal digest;
- exact readiness evidence digest;
- exact pilot handoff digest;
- exact operating contract digest;
- ceremony ID;
- nonce;
- issued/expires timestamps;
- owner public-key ID/version/fingerprint;
- every activation/external-authority flag frozen at false.

The request is signed externally with an Ed25519 owner key from the local
TrustRootRegistry.

## Anti-replay and freshness

The decision window is bounded to a maximum of 180 seconds.

A durable PersistentNonceRegistry claim binds the nonce to:

- owner;
- tenant;
- workspace;
- pilot;
- packet digest;
- request digest;
- key ID/version.

Replay is fail-closed.

## APPROVE_PILOT semantics

A valid signed APPROVE result is only:

`OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE`

It proves the decision signature and prepares a decision record, but keeps:

- owner_decision_recorded=false;
- decision_record_persisted=false;
- pilot_activation_authorized=false;
- pilot_activated=false;
- customer_contact_authorized=false;
- contract_signature_authorized=false;
- billing_authorized=false;
- spend_authorized=false;
- deploy_authorized=false;
- crm_write_authorized=false;
- production_mutation_authorized=false.

The only forward-looking flag is:

`eligible_for_activation_ceremony_after_persistence=true`

which means a later, separate layer may prepare an activation ceremony only
after the decision record has been durably persisted and attested.

## DENY_PILOT semantics

A valid signed DENY result is:

`OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE`

It keeps activation ineligible and all external authority false.

## Generic chat is not a decision

The module explicitly keeps:

`generic_chat_instruction_accepted_as_decision=false`.

A conversational message such as `vamos lá` is never transformed into
`APPROVE_PILOT`.

## Safety boundary

This module never:

- captures the owner's private key;
- performs the signature itself;
- persists the decision record;
- activates the pilot;
- contacts the customer;
- signs a commercial contract;
- bills or spends;
- writes CRM data;
- deploys;
- calls providers;
- mutates production.
