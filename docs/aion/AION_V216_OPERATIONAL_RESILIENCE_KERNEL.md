# AION V2.16 — Operational Observability, Resilience & Recovery Kernel

**Base:** V2.15 hardened head `e9729a00d3cc866c92b30df77fffb7b6a259af92`

## Objetivo

Consolidar as peças já existentes de observabilidade, circuit breaker, resource
governance, journal, recovery e Global Worker em uma postura operacional única,
fail-closed e verificável.

O V2.16 não cria um segundo sistema de resiliência. Ele reaproveita os contratos
existentes e acrescenta os gaps que faltavam para a certificação do núcleo:

- trace/correlation context;
- SLO window explícita;
- bulkhead admission;
- rate limiting;
- backpressure;
- recovery-readiness composta;
- postura operacional canônica.

## Peças reaproveitadas

O repositório já possui:
- `atlasquant_aion_observability.py`;
- `atlasquant_aion_resilience.py`;
- circuit breaker;
- watchdog;
- resource governor;
- safe mode;
- `atlasquant_aion_unified_journal_store.py` append-only/immutable;
- crash recovery determinístico;
- `atlasquant_aion_recovery.py` com restore condicionado e aprovação explícita;
- Global Worker supervision/recovery drill;
- source backup workflow;
- incident/rollback runbook.

O V2.16 compõe essas garantias; não as substitui.

## Trace e correlação

`build_trace_context` usa somente identificadores canônicos:
- request_id;
- task_id;
- execution_id opcional;
- parent span opcional.

O trace não aceita payload de ferramenta nem segredo. O objetivo é permitir que
uma decisão crítica seja reconstruída ponta a ponta sem transportar conteúdo
sensível.

## SLO window

`evaluate_slo_window` exige evidência explícita de:
- request count;
- error count;
- p95 latency;
- queue depth/capacity;
- cost;
- saturation;
- heartbeat age.

Sem tráfego observado, availability não é inventada como 100%. O estado é
`BREACHED` com `SLO_NO_TRAFFIC_EVIDENCE`.

Estados:
- HEALTHY;
- DEGRADED;
- BREACHED.

## Bulkhead

`bulkhead_gate` preserva capacidade reservada para trabalho crítico.

Quando o pool normal chega ao limite não crítico:
- novas tarefas normais são recusadas;
- slots reservados continuam disponíveis para trabalho crítico;
- pool totalmente saturado recusa também crítico.

O gate apenas recomenda admissão. Não despacha tarefa.

## Rate limit

`rate_limit_gate` opera sobre janela explícita:
- ALLOW;
- THROTTLE;
- REJECT_NEW.

Ele não muta limiter remoto nem agenda retry por conta própria.

## Backpressure

`backpressure_gate` cruza:
- queue usage;
- arrival rate;
- service rate.

Estados:
- NORMAL;
- DRAIN_PRIORITY;
- THROTTLE;
- REJECT_NEW.

Fila cheia ou service rate zero diante de entrada positiva rejeita novo trabalho.

## Postura operacional composta

`operational_resilience_view` agrega:
- SLO;
- circuit breaker;
- watchdog;
- resource governor;
- bulkhead;
- rate limit;
- backpressure;
- authority/policy integrity;
- secret exposure;
- Global Kill Switch;
- backup verification;
- restore drill verification;
- deterministic journal recovery verification.

Posturas:
- NORMAL_MONITORED;
- DEGRADED_MONITORED;
- DEGRADED_READ_ONLY;
- EMERGENCY_STOP_RECOMMENDED;
- STOPPED_BY_KILL_SWITCH.

Nenhuma postura concede execução.

Mesmo em `NORMAL_MONITORED`:
- `execution_allowed=False`;
- `external_side_effects_allowed=False`;
- `approval_implied=False`;
- `executes_action=False`.

## Recovery readiness

Para postura normal, o V2.16 exige três evidências separadas:
1. backup verificado;
2. restore drill verificado;
3. journal recovery verificado.

O kernel nunca:
- restaura automaticamente;
- faz rollback automaticamente;
- altera kill switch automaticamente.

## Relação com journal e replay

V2.16 exige:
- journal imutável;
- deterministic replay;
- crash recovery.

A implementação física continua sendo responsabilidade dos stores já existentes.
O kernel não duplica armazenamento.

## Relação com V2.13–V2.15

- V2.13: quem tem authority criptograficamente verificável;
- V2.14: como uma execução é persistida e recuperada com idempotência;
- V2.15: qual capability/tenant/workspace/domain pode ser considerada;
- V2.16: se o ambiente operacional está saudável e resiliente o suficiente para
  sequer prosseguir para gates posteriores.

Nenhuma dessas camadas isoladamente implica execução.

## Critério de fechamento V2.16

- trace determinístico e sem payload/segredo;
- SLO não fabrica saúde sem evidência;
- latency/error/queue/cost/saturation/heartbeat breaches bloqueiam;
- bulkhead preserva reserva crítica;
- rate limit e backpressure reduzem admissão sob pressão;
- circuit breaker/watchdog/resource governor são compostos;
- kill switch domina qualquer sinal verde;
- backup/restore/journal recovery são necessários;
- recovery incompleto impede NORMAL;
- nenhum sinal operacional cria approval ou execution authority;
- Quality/Security/Unified permanecem verdes;
- Release/UI/Mobile permanecem verdes;
- Global Worker permanece separado de ativação real.

## Coordinator hardening

Além das evidências originais, a postura normal exige explicitamente:

- checkpoint integrity verificada;
- audit-chain integrity verificada;
- crash-recovery verification separada de journal recovery.

Esses sinais permanecem independentes de authority, approval e execution.
Ausência de qualquer um deles degrada a postura e nunca produz `execution_allowed=True`.
