# AION B2B — Durable Dispatch Record Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir o write-ahead record durável que deve existir antes de qualquer futuro
`EXTERNAL_EFFECT`.

A semântica obrigatória reutiliza:
`atlasquant_aion_durable_execution_kernel.DurableExecutionStore`

Método de referência:
`DurableExecutionStore.record_dispatch_started`

## Estado máximo

`READY_FOR_DURABLE_DISPATCH_RECORD_DESIGN_REVIEW`

Próximo passo:
`DESIGN_EXTERNAL_EFFECT_CALL_BOUNDARY_CONTRACT_ONLY`

## Estado durável obrigatório

`PREPARED -> LEASED -> DISPATCH_RECORDED`

Nenhum provider pode ser chamado antes de `DISPATCH_RECORDED` estar
duravelmente persistido.

## Invariante crítico

Depois de `DISPATCH_RECORDED`:
- crash => `OUTCOME_UNKNOWN`;
- ambiguidade => `OUTCOME_UNKNOWN`;
- retry automático => proibido;
- reconciliação => explícita;
- reconciliação => com evidência;
- reconciliação => com autorização separada.

## Bindings do record futuro

O record deve ligar execution/task/step, scope, customer/pilot, action/operation,
execution envelope, pre-dispatch attestation, fresh Owner authorization,
authenticated receipt, provider adapter/capability, effective capabilities,
provider identity ref, idempotency/effect key, payload digest, lease identity,
before-state, expected postcondition, rollback/compensation, FinOps,
capacity/quota, observability trace e timestamp.

## Material proibido

O record contém referência/digest, nunca valor real de:
credential, secret, senha, API key/token/private key, auth header/cookie,
endpoint/URL/webhook/callback, HTTP method/headers, payload body,
command/shell/subprocess/PowerShell/curl/script.

## Esta camada NÃO faz

- abrir DurableExecutionStore;
- criar/carregar execution record;
- reservar idempotency/effect key;
- adquirir lease;
- validar lease token real;
- registrar dispatch;
- marcar OUTCOME_UNKNOWN;
- reconciliar;
- resolver endpoint/credencial/payload;
- chamar provider;
- network/billing/CRM/provisioning/deploy/produção.
