# AION B2B — Idempotency + Replay Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir os invariantes duráveis que um futuro executor B2B deverá satisfazer
antes de qualquer implementação com efeito externo ser revisada.

Esta camada reutiliza os princípios já existentes no núcleo AION e NÃO cria uma
segunda fonte de verdade para replay/idempotência.

Componentes de referência do núcleo:

- `atlasquant_aion_nonce_registry.PersistentNonceRegistry`
- `atlasquant_aion_durable_execution_kernel.DurableExecutionStore`
- `atlasquant_aion_durable_execution_kernel.canonical_execution_id`

## Entrada obrigatória

A entrada deve ser o Real Receipt Authenticator Contract em estado:

`READY_FOR_REAL_RECEIPT_AUTHENTICATOR_DESIGN_REVIEW`

com próximo passo:

`DESIGN_IDEMPOTENCY_REPLAY_CONTRACT_ONLY`

Qualquer authority/effect flag ligada bloqueia o avanço.

## Estado máximo

`READY_FOR_IDEMPOTENCY_REPLAY_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_ROLLBACK_COMPENSATION_CONTRACT_ONLY`

## Invariantes obrigatórios

O futuro runtime deverá preservar:

- autenticação antes da reserva de idempotência;
- replay de nonce rejeitado persistentemente;
- idempotency key persistente e única;
- effect key persistente e única;
- execution_id canônico ligado a task/step/idempotency/payload;
- mesma idempotency + mesmo payload = replay seguro;
- mesma idempotency + payload diferente = conflito;
- concorrência duplicada com apenas um vencedor;
- estado durável sobrevivendo reopen/restart;
- lease ownership + lease token;
- recuperação de lease expirado;
- deadline;
- limite de tentativas;
- backoff determinístico;
- registro durável de dispatch antes do efeito externo;
- falha ambígua após dispatch = OUTCOME_UNKNOWN;
- OUTCOME_UNKNOWN sem retry automático;
- falha pré-dispatch podendo tentar novamente somente dentro da política;
- conflito de replay de resultado rejeitado;
- reconciliação explícita para OUTCOME_UNKNOWN;
- reconciliação com evidência;
- reconciliação com autorização separada.

## Estado durável esperado

- PREPARED
- LEASED
- DISPATCH_RECORDED
- RETRY_WAIT
- OUTCOME_UNKNOWN
- COMPLETED
- CANCELED
- DLQ

## Regra crítica para efeito externo

Depois que um dispatch externo for registrado de forma durável, qualquer crash
ou resultado ambíguo deve virar `OUTCOME_UNKNOWN`.

Nesse estado:

- retry automático é proibido;
- o sistema deve exigir reconciliação explícita;
- a reconciliação deve ter evidência;
- a reconciliação deve ter autorização própria;
- autorização histórica não pode ser reaproveitada.

## Bindings mínimos

O futuro registro deverá estar ligado a:

- owner/tenant/workspace;
- customer/pilot;
- action_family/operation_kind;
- execution_request_digest;
- command_plan_digest;
- adapter_plan_digest;
- dry_run_digest;
- rollback_plan_digest;
- authenticated_receipt_digest;
- idempotency_key_digest;
- effect_key_digest;
- payload_digest.

## Esta camada NÃO faz

- claim de nonce;
- escrita em nonce registry;
- reserva de idempotency key;
- reserva de effect key;
- criação de execution record;
- abertura de banco/store;
- lease;
- heartbeat;
- dispatch;
- retry;
- reconciliação;
- provider call;
- network;
- billing;
- customer contact;
- CRM write;
- provisioning;
- deploy;
- produção.

Mesmo com estado READY, todas essas flags continuam false.
