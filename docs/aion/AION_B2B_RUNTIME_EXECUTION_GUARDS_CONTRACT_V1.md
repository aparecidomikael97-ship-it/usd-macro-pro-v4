# AION B2B — Runtime Execution Guards Contract V1

Status: **design-only / provider-neutral / non-executable**.

## Objetivo

Definir os guardrails que um futuro runtime deverá provar imediatamente antes
de qualquer external effect.

Esta camada não seleciona provider e não cria executor.

## Estado máximo

`READY_FOR_RUNTIME_EXECUTION_GUARDS_DESIGN_REVIEW`

Próximo passo:

`DESIGN_PROVIDER_ADAPTER_ATTESTATION_CONTRACT_ONLY`

## Guardrails obrigatórios

- autorização fresca do Owner verificada no momento do dispatch;
- autorização single-use e não expirada;
- binding exato owner/tenant/workspace/customer/pilot/package/action;
- zero production scope expansion;
- capability allowlist mínima;
- tenant isolation;
- idempotency/effect-key persistentes;
- lease ownership;
- dispatch registrado antes do efeito;
- OUTCOME_UNKNOWN fail-closed;
- rollback/compensation class vinculada;
- irreversible boundary fail-closed;
- FinOps runtime cap de 20.000 centavos;
- evidência de custo por ação;
- capacity reservation + quota;
- provider adapter attestation;
- provider/writer identity binding;
- security/privacy incident fail-closed;
- circuit breaker;
- kill switch;
- before/after state evidence;
- observability trace;
- audit receipt.

## Observabilidade mínima

O futuro receipt/trace deve ligar execution_id, scope, customer/pilot,
action/operation, authorization digest, authenticated receipt, idempotency,
effect identity, provider/writer identity, before/after state, rollback plan,
FinOps estimate, timestamps e outcome.

## Esta camada NÃO faz

- consumo de autorização;
- reservation de capacity/quota;
- charge reservation;
- provider attestation real;
- identity verification real;
- arm de circuit breaker/kill switch;
- escrita de audit receipt;
- escrita de observability event;
- provider selection/call;
- network;
- billing;
- CRM;
- deploy;
- produção.
