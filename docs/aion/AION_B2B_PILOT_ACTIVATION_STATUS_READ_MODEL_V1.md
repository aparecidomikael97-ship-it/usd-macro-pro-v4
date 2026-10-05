# AION B2B Pilot Activation Governance Read Model V1

Status: **staging / read-only UI projection / no authority**.

## Objective

Expose the validated B2B pilot activation-governance state inside
`Negócios -> Automação B2B` without exposing execution controls or sensitive
evidence.

## Source

The read model consumes only a clean
`ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PREFLIGHT_V1` result.

The source must be:

- `READY_FOR_ACTIVATION_EXECUTION_CEREMONY`;
- bound to the trusted owner/tenant/workspace;
- execution-ceremony eligible;
- still requiring human execution confirmation;
- free of blockers;
- free of any execution or external-action authority.

## Exposed aggregate state

The cockpit may show:

- pilot ID;
- pilot decision: ATTESTED;
- activation preflight: ATTESTED;
- activation authorization: ATTESTED;
- activation persistence: ATTESTED;
- activation writer: ATTESTED;
- execution environment: VERIFIED;
- execution: BLOCKED_PENDING_HUMAN_CONFIRMATION;
- monthly infrastructure cap: R$200.

## Deliberately hidden

The read model never exposes:

- candidate identity;
- proposal/customer identity beyond the pilot label used by the cockpit;
- cryptographic digests;
- raw evidence references;
- writer key/fingerprint;
- nonce/signature material;
- activation controls;
- activation commands.

## UI truth

When valid, the B2B panel displays:

`GOVERNANÇA VALIDADA · AGUARDANDO CONFIRMAÇÃO HUMANA · SEM COMANDO DE ATIVAÇÃO`

The global execution status remains `BLOQUEADA`.

## Safety boundary

The read model and UI are strictly read-only:

- no automatic activation;
- no customer contact;
- no billing;
- no provisioning;
- no deploy;
- no CRM write;
- no provider call;
- no production mutation;
- no authority grant;
- no execution.
