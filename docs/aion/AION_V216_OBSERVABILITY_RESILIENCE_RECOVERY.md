# AION V2.16 — Observability, Resilience & Recovery Kernel

**Base:** V2.15 hardened head `e9729a00d3cc866c92b30df77fffb7b6a259af92`

## Objetivo

Consolidar a postura operacional do AION em um contrato único, determinístico e
fail-closed, reaproveitando os módulos já existentes de observabilidade, journal,
worker supervision, recovery drill, durable execution e kill switch.

O V2.16 não substitui essas peças. Ele consome evidência explícita e responde:

- `HEALTHY`
- `DEGRADED`
- `BLOCKED`

Mesmo em `HEALTHY`:
- `execution_allowed=false`
- `approval_implied=false`
- `authority_implied=false`

Resiliência não é autoridade.

## Evidência obrigatória

### Métricas
- p95 latency;
- error rate;
- saturation;
- queue depth;
- retry backlog.

### Integridade
- journal verified;
- audit chain verified;
- checkpoint verified.

### Recovery
- backup verified;
- restore drill passed;
- journal replay verified;
- crash recovery verified.

### Runtime
- runtime health confirmado;
- kill switch explicitamente liberado para avaliar postura de execução;
- runtime não-read-only.

### Dependências
Circuit breakers precisam ter estado canônico:
- CLOSED
- OPEN
- HALF_OPEN

## Backpressure

O kernel retorna:
- ACCEPT;
- THROTTLE;
- REJECT_NEW_WORK.

Ele não altera fila nem agenda tarefa.

Soft limits produzem DEGRADED.
Hard limits produzem BLOCKED.

## Circuit breaker

A transição é determinística:
- CLOSED -> OPEN por failure count ou rolling error rate;
- OPEN -> HALF_OPEN somente após cooldown explícito;
- HALF_OPEN -> CLOSED apenas com probe success explícito;
- HALF_OPEN -> OPEN com probe failure.

Nenhuma transição chama dependência.

## Kill switch

Se `global_kill_switch != false`, a postura é BLOCKED.

Isso não muda o kill switch. O V2.16 apenas observa evidência.

## Relação com componentes existentes

O V2.16 consolida contratos já presentes em:
- `atlasquant_aion_observability.py`;
- `atlasquant_aion_unified_journal.py`;
- `atlasquant_aion_unified_journal_store.py`;
- `atlasquant_aion_global_worker_supervision.py`;
- `atlasquant_aion_global_worker_recovery_drill.py`;
- `atlasquant_aion_worker_runtime.py`;
- `atlasquant_aion_durable_execution_kernel.py`.

## Critério de fechamento

- métricas canônicas e bounded;
- soft/hard SLO thresholds;
- backpressure determinístico;
- circuit breaker CLOSED/OPEN/HALF_OPEN;
- integrity evidence obrigatória;
- recovery evidence obrigatória;
- kill switch fail-closed;
- runtime health fail-closed;
- malformed/NaN/infinite metrics rejeitadas;
- payload não consegue fabricar authority/approval/execution;
- todos os gates canônicos verdes.

## Não objetivos

Este bloco não:
- arma worker;
- liga feature flag;
- executa provider;
- envia mensagem;
- faz pagamento;
- publica;
- faz trading;
- executa backup/restore real;
- concede approval;
- concede authority;
- libera execução.
