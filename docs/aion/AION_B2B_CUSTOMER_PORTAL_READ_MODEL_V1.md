# AION B2B Customer Portal Read Model V1

Status: **staging / read-only / evidence-bound**.

## Purpose

Expose managed-service evidence inside the Negócios cockpit without giving the UI
any operational authority.

The read model is built only from:

- the reviewed Managed Service contract;
- a presentable managed-service cycle;
- tenant-scoped usage evidence;
- tenant-scoped support/SLA evidence;
- explicit evidence references.

## Published fields

When evidence validates, the UI may display:

- customer ID;
- approved package;
- managed-service state and review decision;
- customer health score;
- observed ROI;
- observed service cost;
- capacity utilization;
- call utilization;
- token utilization;
- support-ticket utilization;
- average first-response time;
- average resolution time;
- critical open-ticket count;
- SLA-met indicators;
- review/incident reasons;
- evidence timestamp.

Missing, malformed, crossed-tenant, or authority-bearing data is not displayed as
validated customer evidence.

## UI behavior

The Negócios home shows a validated summary only when:

- schema is ATLASQUANT_AION_B2B_PORTAL_READ_MODEL_V1;
- state is READY;
- read_only=true;
- grants_authority=false;
- executes_action=false.

Otherwise it shows that customer metrics are awaiting validated evidence.

The detailed routes for ROI, FinOps, Saúde do Cliente and SLA may render the same
bounded snapshot. They do not call providers or recalculate commercial decisions.

## Safety boundary

read_only=true.
grants_authority=false.
automatic_renewal=false.
automatic_billing=false.
automatic_quota_change=false.
automatic_role_change=false.
automatic_customer_contact=false.
automatic_deploy=false.
production_mutation=false.
executes_action=false.

There are deliberately no UI controls for direct renewal, billing, quota expansion,
role changes or production activation in this read model.
