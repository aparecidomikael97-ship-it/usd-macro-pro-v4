# AION B2B Customer Portal V1

Status: **staging / credential-bound / read-only / route not auto-exposed**.

## Purpose

Provide a customer-facing portal without exposing the administrative Negócios
workspace or internal operating data.

The customer portal is a separate surface. A normal customer does not gain access
to the ADMIN Negócios cockpit.

## Identity chain

Access is fail-closed and requires the complete chain:

1. authenticated AtlasQuant USER session;
2. credential-bound AION tenant namespace;
3. CONFIRMED and enabled B2B customer-portal binding;
4. exact B2B service tenant;
5. exact service workspace;
6. exact customer ID;
7. exact approved package;
8. READY, read-only, authority-free B2B portal read model.

Credential rotation changes the authentication tenant namespace, so an old binding
cannot silently follow a replaced credential.

ADMIN and SALES roles cannot impersonate the customer through this surface.

## Customer-visible data

The customer-safe view may expose only approved sections from:

- overview;
- value;
- usage;
- support.

The current V1 can show:

- contracted package;
- service state;
- customer health;
- observed ROI;
- capacity usage;
- call usage;
- token usage;
- support-ticket usage;
- average first-response time;
- average resolution time;
- SLA indicators;
- review / incident notices;
- evidence timestamp.

## Deliberately hidden

The customer-safe view does not expose:

- internal service operating cost;
- owner ID or internal owner scope;
- ADMIN memory;
- another tenant's data;
- other customers;
- internal commercial policy;
- internal pricing/margin logic;
- secrets or credentials.

## Route exposure

This module includes a rendering adapter but does not auto-register a public route.

A host must explicitly supply:

- the authenticated access object;
- the confirmed customer binding;
- the validated customer read model.

Without all three, the portal renders a blocked/no-data state.

## Safety boundary

read_only=true.
admin_memory_access=false.
other_tenant_access=false.
internal_service_cost_exposed=false.
owner_scope_exposed=false.
grants_authority=false.
automatic_billing=false.
automatic_renewal=false.
automatic_quota_change=false.
automatic_role_change=false.
automatic_customer_contact=false.
automatic_deploy=false.
production_mutation=false.
executes_action=false.

The V1 intentionally contains no direct "charge", "renew", "increase quota",
"change role", "publish", or "deploy" action.
