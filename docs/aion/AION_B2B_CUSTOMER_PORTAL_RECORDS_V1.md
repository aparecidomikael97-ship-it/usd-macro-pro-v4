# AION B2B Customer Portal Records V1

Status: **staging / read-only / tenant-scoped**.

## Purpose

Add safe customer-facing metadata for:

- integrations;
- CRM summary;
- documents;
- subscription/payment status.

This layer is presentation evidence only. It does not execute any operational,
financial, contractual or provider action.

## Scope binding

Every record package must match the trusted:

- owner scope;
- service tenant;
- workspace;
- customer ID;
- package.

A mismatch blocks the complete record package.

## Secret rejection

The normalizer rejects nested fields whose keys resemble:

- password;
- secret;
- token;
- API key;
- credential;
- authorization.

Secret-like input is never copied into the normalized output.

## Integrations

Customer-visible integration metadata is limited to:

- integration ID;
- display name;
- state;
- last checked timestamp.

Allowed states:

- CONNECTED;
- DEGRADED;
- DISCONNECTED;
- PENDING.

No token, webhook secret, credential, configuration payload or provider mutation is exposed.

## CRM

CRM exposure is summary-only:

- contact count;
- open opportunity count;
- open task count;
- wins in the current cycle.

No contact names, phone numbers, email addresses or message content are included.

## Documents

Document metadata can expose:

- document ID;
- title;
- type;
- state;
- issue date;
- version.

The V1 does not sign documents, upload files, generate signatures or expose raw
storage paths.

## Billing and subscription

Read-only fields:

- subscription state;
- payment state;
- next due date;
- amount due in BRL.

Allowed subscription states:

- ACTIVE;
- PENDING;
- PAUSED;
- CANCELLED;
- NOT_APPLICABLE.

Allowed payment states:

- PAID;
- DUE;
- OVERDUE;
- NOT_APPLICABLE.

No payment link is created and no charge is attempted.

## Safety boundary

read_only=true.
secret_material_exposed=false.
payment_link_created=false.
document_signed=false.
automatic_billing=false.
automatic_subscription_change=false.
automatic_crm_write=false.
automatic_integration_change=false.
provider_called=false.
production_mutation=false.
executes_action=false.
