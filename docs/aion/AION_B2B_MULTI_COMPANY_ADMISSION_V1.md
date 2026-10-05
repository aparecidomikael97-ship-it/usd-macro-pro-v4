# AION B2B Multi-Company Admission & Tenant Quota Gate V1

Status: **staging / admission planning only / no provisioning**.

## Objective

Decide whether an evidence-backed managed-service candidate may enter a human
tenant-admission review without overbooking AtlasQuant capacity or weakening
tenant isolation.

This layer is downstream of:

- Pilot Value Realization;
- Pilot-to-Managed-Service Conversion & Capacity.

Both upstream layers must be clean and reviewable.

## Tenant identity

The admission request requires:

- exact trusted owner/tenant/workspace scope;
- customer ID matching the commercial conversion;
- safe unique service tenant ID;
- package matching the commercial recommendation;
- requested per-tenant quotas;
- channel count;
- integration count;
- expected peak utilization;
- evidence references.

A service tenant ID that already exists produces ISOLATION_HOLD.
An already-admitted customer also produces ISOLATION_HOLD.

## Per-tenant quotas

Four quota dimensions are controlled:

- capacity units;
- calls per cycle;
- tokens per cycle;
- support tickets per cycle.

The gate calculates current allocation, requested allocation, projected total,
portfolio limit, reserve percentage and single-tenant share for every dimension.

## Portfolio policy

A VERIFIED policy defines:

- maximum active tenants;
- portfolio limits for each quota dimension;
- minimum reserve percentage;
- maximum single-tenant share;
- maximum per-tenant utilization before noisy-neighbor review;
- maximum channels per tenant;
- maximum integrations per tenant.

Policy and portfolio each require at least four evidence references.

## Noisy-neighbor protection

Every active tenant provides utilization percentages per quota dimension.

If any existing tenant is above the configured utilization threshold, new
admission enters CAPACITY_HOLD. This prevents growth from silently degrading
already-served customers.

The candidate's expected peak utilization is checked against the same boundary.

## Reserve and concentration

Admission enters CAPACITY_HOLD when any of the following occurs:

- active-tenant maximum exceeded;
- hard portfolio quota exceeded;
- reserve falls below policy;
- single-tenant concentration exceeds policy;
- channel or integration limit exceeded;
- candidate peak utilization exceeds policy;
- an existing noisy-neighbor signal is present.

## Decisions

- REVIEWABLE / TENANT_ADMISSION_REVIEW_CANDIDATE;
- CAPACITY_HOLD / CAPACITY_REVIEW;
- ISOLATION_HOLD / ISOLATION_REVIEW;
- BLOCKED / BLOCKED.

Every result remains owner-review only.

## Safety boundary

owner_admission_approval_required=true.
tenant_creation_authorized=false.
quota_change_authorized=false.
admission_token_issued=false.
automatic_tenant_creation=false.
automatic_quota_change=false.
automatic_package_change=false.
automatic_pricing_change=false.
automatic_contract_change=false.
automatic_billing=false.
automatic_provisioning=false.
automatic_customer_contact=false.
automatic_deploy=false.
crm_write=false.
provider_called=false.
production_mutation=false.
executes_action=false.
