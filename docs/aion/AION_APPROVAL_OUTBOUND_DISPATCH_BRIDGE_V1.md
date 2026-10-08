# AION Approval Decision + Outbound Dispatch Bridge V1

Status: IMPLEMENTATION SAFE / NON-EXECUTING BRIDGE  
Date: 2026-10-08  
Stacked base: Contract + Communication Draft & Approval V1  
Outbound action executed: NO  
Production status: NOT DEPLOYED

## Objective

Define the fail-closed bridge between an exact human-approved draft and a future
outbound execution adapter.

This block covers the transition:

`PENDING_HUMAN_APPROVAL -> APPROVED EVIDENCE -> DISPATCH BRIDGE REVIEW`

It deliberately stops before execution authorization, durable dispatch and any
real external effect.

## Critical invariant: exact approved content

Approval binds the exact subject digest.

Before preparing the outbound bridge, the module recalculates the current draft
digest from the actual draft content.

It verifies:

1. stored draft digest;
2. rebuilt current draft digest;
3. approval packet subject digest;
4. human approval decision evidence subject digest.

All four must agree.

If the draft changes after approval, even by one character, the bridge blocks.

There is no concept of:

- approximately the same message;
- equivalent wording;
- minor harmless edit after approval;
- approval inherited by a revised version.

A revised draft requires a new approval packet and new human decision.

## Reuse of existing ApprovalGate semantics

The repository already has Core ApprovalGate semantics where an APPROVED
decision does **not** set execution_authorized=true.

This V1 preserves that separation.

Approval evidence therefore reports:

- approval_is_execution_authorization=false
- execution_authorized=false
- approval_consumed_by_this_module=false

The outbound bridge can only reach:

`READY_FOR_EXECUTION_AUTHORIZATION_REVIEW`

It cannot reach SENT, EXECUTED or SIGNED.

## Human approval decision evidence

A future trusted ApprovalGate adapter must produce evidence binding:

- approval ID;
- approval version;
- APPROVED or REJECTED decision;
- logical human principal reference;
- human principal binding digest;
- owner binding digest;
- authenticated human receipt digest;
- exact approval-packet digest;
- exact approved subject digest;
- requested action;
- decision time;
- expiry time;
- authenticated human receipt verification;
- owner session/signature verification;
- consumed state.

The approval window in V1 may not exceed five minutes.

The bridge also checks current freshness before accepting the evidence.

## Rejected decisions

REJECTED evidence can be represented truthfully but cannot enter an outbound
bridge.

Only:

`APPROVED_EVIDENCE_READY`

is accepted.

## Single use

An already consumed approval is blocked.

This module does not itself consume the approval because consumption belongs to
the future execution-authorization/durable-dispatch layer.

The bridge requires a future single-use execution authorization before any real
dispatch.

## Adapter manifest

The outbound adapter is described through a signed logical manifest.

Supported logical adapter kinds:

- EMAIL_PROVIDER
- WHATSAPP_PROVIDER
- CONTRACT_EXPORT_ADAPTER

Supported capabilities:

- SEND_EMAIL
- SEND_WHATSAPP
- EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW

The action and adapter kind must match exactly.

Examples:

- SEND_EMAIL -> EMAIL_PROVIDER
- SEND_WHATSAPP -> WHATSAPP_PROVIDER
- EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW -> CONTRACT_EXPORT_ADAPTER

An adapter allowlist is a ceiling, not authority.

A signed adapter manifest does not authorize sending.

## No provider switching

The bridge binds the exact adapter identity and signed manifest digest.

V1 forbids dynamic provider switching after approval.

A future adapter change requires the bridge to be rebuilt and the downstream
execution authorization to revalidate the exact new binding.

## Recipient/endpoint/credential separation

This contract contains no:

- raw email address;
- raw phone number;
- provider endpoint URL;
- authorization header;
- API key;
- password;
- access token;
- refresh token;
- private key;
- raw provider payload.

Those belong only inside a future trusted adapter immediately before dispatch
and after all authorization gates.

## Idempotency and effect identity

The bridge requires:

- idempotency-key digest;
- effect-key digest.

They must be distinct.

These values prepare the future durable execution boundary for duplicate-effect
protection.

The bridge itself does not reserve or persist either key.

## Remaining mandatory gates

A READY bridge explicitly says that the following are still required:

1. fresh single-use execution authorization;
2. immediate pre-dispatch revalidation;
3. durable dispatch record written before external effect;
4. outcome receipt after the attempt.

Therefore an approved draft alone can never reach a provider.

## Crash / ambiguous outcome philosophy

The future outbound executor must follow the same fail-closed principle already
used elsewhere in AION:

- durable dispatch marker before effect;
- after dispatch marker, timeout/crash/ambiguous acknowledgement becomes
  OUTCOME_UNKNOWN;
- OUTCOME_UNKNOWN cannot be automatically retried;
- reconciliation must be separate and evidence-based.

This V1 prepares the bindings but does not write that dispatch record.

## Contract export

Approval for:

`EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW`

does not mean:

- SIGN_CONTRACT;
- REQUEST_SIGNATURE;
- legal acceptance.

The bridge binds only a future contract-export adapter.

Even a READY bridge reports:

- contract_exported=false
- signature_requested=false

## State boundaries

A positive bridge still reports:

- approval_consumed=false
- execution_authorization_issued=false
- execution_authorized=false
- dispatch_record_written=false
- recipient_resolved=false
- endpoint_resolved=false
- credentials_loaded=false
- payload_materialized=false
- provider_called=false
- network_called=false
- message_sent=false
- contract_exported=false
- signature_requested=false
- external_action_executed=false

## Relationship to the owner stack

The owner-safe chain now becomes:

1. Owner Experience V1
2. Cognitive Memory + Continuity V1
3. Secure Local Agent V1
4. Local Action Audit Receipt V1
5. Secure Desktop Runtime Blueprint V1
6. Voice + Hotword Runtime V1
7. Teaching + Meeting Orchestrator V1
8. Presentation Artifact + Control V1
9. Advisor + Decision Support V1
10. Contract + Communication Draft & Approval V1
11. Approval Decision + Outbound Dispatch Bridge V1

## Explicitly absent

This block does not:

- approve a pending approval;
- verify Windows Hello/FIDO2 itself;
- consume approval;
- issue execution authorization;
- resolve email/phone;
- resolve provider endpoint;
- load credentials;
- materialize provider payload;
- call Gmail/SMTP;
- call WhatsApp;
- export a real contract file;
- request e-signature;
- send a message;
- write CRM;
- write durable dispatch record;
- start Worker;
- deploy;
- modify frozen Core V1.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_APPROVAL_OUTBOUND_DISPATCH_BRIDGE_V1_CONTRACT_VALIDATED`

That validates the exact-draft/approval/adapter bridge only.

It does not mean any external communication or contract export was executed.
