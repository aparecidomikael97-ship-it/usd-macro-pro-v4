# AION Contract + Communication Draft & Approval V1

Status: IMPLEMENTATION SAFE / DRAFT + APPROVAL PACKET ONLY  
Date: 2026-10-08  
Stacked base: AION Advisor + Decision Support V1  
Contract signed: NO  
Email sent: NO  
WhatsApp sent: NO  
Production status: NOT DEPLOYED

## Objective

Give AION a safe owner-facing workflow for:

- drafting contracts;
- summarizing clauses;
- binding high-risk clauses to Advisor findings;
- drafting client email;
- drafting client WhatsApp;
- preparing an exact human-approval packet.

This V1 deliberately stops before signature or message transmission.

## Core state separation

The mandatory lifecycle is:

`DRAFT_READY != APPROVED != EXECUTION_AUTHORIZED != SENT/SIGNED`

A draft never becomes an external action merely because it exists.

An approval packet never approves itself.

Even a future APPROVED state must remain separate from physical execution.

## Contract drafts

A contract draft binds:

- contract ID;
- title;
- version;
- logical party references;
- source references;
- optional jurisdiction reference;
- ordered clause records;
- clause body digest;
- clause summary;
- clause source reference;
- clause state;
- clause risk severity;
- optional Advisor risk references;
- contract digest.

A contract draft always reports:

- legal_review_required=true
- contract_is_final_legal_document=false
- legal_advice_issued=false
- binding_commitment_created=false
- contract_signed=false
- signature_requested=false
- signature_collected=false

## High-risk clauses

HIGH or CRITICAL clause risk requires:

- a valid Advisor assessment;
- the Advisor assessment to be in a reviewable state;
- one or more Advisor risk IDs;
- those risk IDs to exist in the exact bound Advisor assessment.

This prevents a contract from labeling a clause "Advisor reviewed" without
binding the actual risk record.

The contract layer itself never issues a legal conclusion.

## Logical parties and recipients

The control plane uses logical references instead of raw contact locators.

Examples:

- `party://client-1`
- `contact://client-1/primary`
- `crm://client-1/whatsapp-primary`

The contract/message planner does not store or resolve:

- raw email addresses;
- raw phone numbers;
- provider tokens;
- SMTP credentials;
- WhatsApp credentials.

Real contact resolution belongs to a future external adapter after approval.

## Email draft

An email draft requires:

- channel EMAIL;
- logical recipient reference;
- subject;
- message body;
- optional attachment references;
- optional contract/proposal digest;
- optional CRM conversation reference;
- deterministic draft digest.

It always reports:

- recipient_address_resolved=false
- approved=false
- execution_authorized=false
- message_sent=false
- provider_called=false
- network_called=false

## WhatsApp draft

A WhatsApp draft requires:

- channel WHATSAPP;
- logical recipient reference;
- message body.

The EMAIL-only subject field is removed for WhatsApp.

It does not resolve the phone number or call WhatsApp.

## Approval packet

A READY communication/contract draft can produce a deterministic owner approval
packet.

Supported requested actions:

- SEND_EMAIL
- SEND_WHATSAPP
- EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW

These map to the existing Core approval class:

`EXTERNAL_CHANGE`

This module does not call or replace ApprovalGate.

The packet binds:

- requested action;
- subject type;
- exact draft/contract digest;
- owner binding digest;
- reason;
- approval packet digest.

Its state is:

`PENDING_HUMAN_APPROVAL`

and it explicitly reports:

- approved=false
- rejected=false
- approval_decision_recorded=false
- approval_receipt_verified=false
- execution_authorized=false
- approval_is_execution=false

## Why export-for-signature-review is not signing

The contract action intentionally says:

`EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW`

not:

`SIGN_CONTRACT`

This V1 does not possess signature authority.

A later signature workflow must separately define:

- exact final document digest;
- signer identity;
- signature provider/ceremony;
- legal/professional review status;
- owner approval;
- receipt and final signed artifact.

## Relationship to ApprovalGate

The repository already has a Core ApprovalGate where even an APPROVED decision
sets:

`execution_authorized=false`

This contract preserves that architecture.

A future outbound adapter must independently verify both approval and execution
authorization before sending anything.

## Advisor integration

Contract drafting can consume the Advisor + Decision Support assessment from the
previous block.

This makes the intended owner workflow:

1. evidence review;
2. Advisor risk/recommendation;
3. contract draft/revision;
4. owner review;
5. approval packet;
6. separate approval decision;
7. separate execution adapter;
8. delivery/signature receipt.

## Explicitly absent

This block does not:

- resolve a client email address;
- resolve a client phone number;
- send email;
- send WhatsApp;
- call Gmail/SMTP;
- call WhatsApp API;
- sign a contract;
- request an e-signature;
- create a legal conclusion;
- write CRM;
- write memory;
- activate Worker;
- deploy;
- write frozen Core checkpoint.

## Validation target

After dedicated CI is green, the maximum truthful state is:

`AION_CONTRACT_COMMUNICATION_DRAFT_APPROVAL_V1_CONTRACT_VALIDATED`

That validates drafting and approval-packet semantics only.

It does not mean any contract has been signed or any message has been sent.
