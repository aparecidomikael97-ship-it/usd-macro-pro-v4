# AION B2B Managed Service Control V1

Status: **staging / Draft-only / owner activation required**.

## Purpose

Define a bounded recurring managed-service contract after a customer has passed:

1. controlled pilot;
2. pilot outcome / customer health review;
3. commercial conversion / capacity review.

This layer controls recurring service terms and evaluates one operating cycle. It
does not sign, bill, provision, deploy, renew, pause, terminate or contact the
customer automatically.

## Managed-service contract

The contract requires:

- exact owner / tenant / workspace binding;
- exact customer and approved package;
- owner commercial approval reference;
- monthly price and monthly service-cost cap;
- capacity-unit quota;
- call quota;
- token quota;
- support-ticket quota;
- first-response SLA;
- resolution SLA;
- bounded allowed workflows;
- integration references;
- complete RBAC role set:
  - OWNER;
  - ADMIN;
  - MANAGER;
  - COLLABORATOR;
- at least five evidence references.

A service-cost cap that removes the contracted positive margin is blocked.

## Recurring evidence

Each service cycle is reviewed against:

- owner activation attestation;
- tenant isolation evidence;
- cross-tenant posture;
- FinOps state and actual service cost;
- capacity, call, token and support quotas;
- support first-response / resolution SLA;
- critical support tickets;
- customer health score;
- observed customer ROI/value.

## Decision states

- HEALTHY / RENEWAL_REVIEW_CANDIDATE;
- REMEDIATION / REMEDIATE_REVIEW;
- CAPACITY_HOLD / CAPACITY_REVIEW;
- INCIDENT_REVIEW;
- BLOCKED.

Even HEALTHY only creates a renewal review candidate. It never renews automatically.

## Incident boundary

Any tenant security incident, privacy incident or scope breach returns
INCIDENT_REVIEW.

The control layer does not automatically pause or terminate the customer because
those are consequential owner decisions.

## Quota boundary

Any configured quota breach returns CAPACITY_REVIEW:

- capacity units;
- calls;
- tokens;
- support-ticket count.

The system never raises quotas automatically.

## SLA and value boundary

SLA misses, FinOps degradation, health below target, or negative observed customer
value produce REMEDIATE_REVIEW.

This keeps retention tied to demonstrated value rather than automatic renewal.

## Safety boundary

owner_activation_required=true.
automatic_activation=false.
automatic_contract_signature=false.
automatic_billing=false.
automatic_provisioning=false.
automatic_integration_enablement=false.
automatic_role_grant=false.
automatic_renewal=false.
automatic_pause=false.
automatic_termination=false.
automatic_quota_increase=false.
automatic_role_change=false.
automatic_integration_change=false.
automatic_customer_contact=false.
automatic_deploy=false.
production_mutation=false.
executes_action=false.
