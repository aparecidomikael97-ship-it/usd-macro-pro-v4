# AION V2.14 — Durable Execution Safety Kernel

**Base:** V2.13 head `b0495d0d0ca025b25c741bfc3dbcfe5b07448f93`

## Objetivo

Fechar a semântica de execução durável do AION sem transformar o núcleo em executor
autônomo irrestrito.

O repositório já possuía:
- durable tasks com task id, revision/CAS, idempotency history e retry local seguro;
- checkpoint/resume;
- cancelamento;
- taskgraph persistente;
- Global Worker com lease e heartbeat.

O V2.14 **não substitui** essas peças. Ele adiciona um kernel persistente que unifica
a segurança em volta de um executor, especialmente no caso de efeitos externos.

## Problema central

O cenário mais perigoso é:

1. o AION registra uma tarefa;
2. inicia uma chamada externa;
3. a chamada pode ter produzido efeito;
4. o processo cai antes de receber ou persistir a resposta;
5. após restart, um retry automático pode duplicar o efeito.

O V2.14 proíbe esse retry automático.

## Estados

- PREPARED
- LEASED
- DISPATCH_RECORDED
- RETRY_WAIT
- OUTCOME_UNKNOWN
- COMPLETED
- CANCELED
- DLQ

## Regra de efeito externo

Para `EXTERNAL_EFFECT`:

- antes do dispatch: falha pode ser retryable;
- o dispatch deve ser registrado durablemente antes do handoff ao executor;
- depois de `DISPATCH_RECORDED`, falha/crash ambíguo vira `OUTCOME_UNKNOWN`;
- `OUTCOME_UNKNOWN` nunca é automaticamente leased/retryado;
- somente reconciliação explícita e evidenciada pode concluir:
  - `CONFIRMED_EFFECT` -> COMPLETED;
  - `CONFIRMED_NO_EFFECT` -> RETRY_WAIT.

Essa política prioriza não duplicar efeitos sobre disponibilidade.

## Idempotência e deduplicação

O kernel usa:
- task_id existente do Durable Tasks;
- step_id;
- idempotency_key;
- effect_key;
- payload_digest.

O `execution_id` é derivado deterministicamente.

Repetir a mesma idempotency key com o mesmo contrato devolve replay.
Reutilizar a mesma idempotency key com payload/escopo diferente é conflito.
Registrar o mesmo effect_key com outra execução é bloqueado.

## Retry e backoff

Retry antes de dispatch:
- exponential backoff determinístico;
- limite por max_attempts;
- deadline global;
- fingerprint de erro;
- poison threshold;
- DLQ ao atingir limite, erro não retryable, poison task ou deadline.

Não há jitter nesta camada porque replay e teste devem ser determinísticos. Jitter de
scheduler pode ser aplicado fora do contrato desde que nunca antecipe `next_attempt_at`.

## Lease e heartbeat

A execução precisa de lease com:
- owner;
- token;
- expires_at;
- heartbeat;
- lease conflict fail-closed.

Lease expirada antes de dispatch pode retornar a RETRY_WAIT.
Lease expirada depois de dispatch vira OUTCOME_UNKNOWN.

## Cancelamento

Cancelamento é seguro antes de dispatch.
Depois de dispatch ou em outcome unknown, cancelamento não pode fingir que o efeito
não aconteceu.

## Persistência

SQLite local com:
- WAL;
- synchronous FULL;
- transações `BEGIN IMMEDIATE`;
- estado preservado após reopen/restart.

## O que este módulo NÃO faz

- não chama provider;
- não envia e-mail;
- não faz pagamento;
- não publica;
- não faz trading;
- não ativa Global Worker;
- não decide approval;
- não concede capability;
- não executa ação externa.

`executes_action=False` e `external_effect_performed=False` permanecem explícitos.

## Relação com V2.13

V2.13 prova **quem/qual autoridade** concedeu capability.
V2.14 controla **como uma execução autorizada seria persistida e recuperada**.

Ainda falta o V2.15 para isolamento/capability security e o Policy Kernel posterior
para compor a decisão final.

## Critério de fechamento V2.14

- idempotency replay provado;
- efeito duplicado bloqueado;
- lease concorrente permite um único owner;
- heartbeat/token verificados;
- retry/backoff/deadline provados;
- DLQ e poison task provados;
- restart antes de dispatch é recuperável;
- restart após dispatch -> OUTCOME_UNKNOWN;
- OUTCOME_UNKNOWN sem retry automático;
- reconciliação exige autorização booleana exata + evidence digest;
- cancelamento pós-dispatch bloqueado;
- persistência após reopen;
- todos os gates canônicos verdes.
