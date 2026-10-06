# AION B2B Multi-Company Admission Read Model V1

Status: **staging / admin read-only projection**.

## Objective

Expose admission and portfolio-capacity status under
`Negócios -> Empresas / Clientes` without exposing identities of other tenants
or any tenant/quota mutation control.

## Published fields

The Admin view may display:

- candidate service tenant ID;
- recommended package;
- projected active-tenant count;
- requested/projected/limit values per quota dimension;
- minimum remaining portfolio reserve;
- maximum candidate concentration;
- count of capacity review reasons;
- count of isolation review reasons;
- admission state and decision.

## Deliberately hidden

The projection never publishes:

- customer ID;
- identities of other tenants;
- other customer names or IDs;
- raw portfolio evidence;
- policy evidence;
- provider credentials;
- tenant-creation controls;
- quota-change controls;
- provisioning controls;
- billing controls.

## UI truth

The cockpit displays:

`CAPACIDADE & ADMISSÃO · SOMENTE LEITURA · SEM CRIAÇÃO DE TENANT OU QUOTA`

The global execution status remains BLOQUEADA.

## Safety boundary

read_only=true.
other_tenant_identity_exposed=false.
customer_identity_exposed=false.
tenant_creation_control_exposed=false.
quota_control_exposed=false.
provisioning_control_exposed=false.
billing_control_exposed=false.
grants_authority=false.
executes_action=false.
