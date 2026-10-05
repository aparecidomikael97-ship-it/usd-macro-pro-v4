# ADR-0015 — Postura operacional é interseção de sinais e nunca autoridade de execução

- Título: Postura operacional é interseção de sinais e nunca autoridade de execução
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION possui circuit breaker, watchdog, resource governor, journal durável,
recovery e múltiplas fontes de health. O ecossistema também precisa operar sob
carga, saturação, indisponibilidade de provider e degradação parcial.

## Problema

Um único indicador verde não prova que o ambiente está seguro para continuar.
Health, SLO, queue, circuit, recovery ou heartbeat isolados podem estar saudáveis
enquanto outro subsistema está degradado.

Também seria perigoso transformar observabilidade em autorização: uma métrica
saudável não é approval, authority ou capability.

## Alternativas consideradas

Foram rejeitados:
- health geral baseado em média;
- SLO verde implicando execution_allowed;
- retry indiscriminado para aliviar fila;
- remover backpressure em favor de throughput;
- compartilhar um único pool sem bulkhead;
- recovery automático diante de falha;
- kill switch controlado pelo próprio agente.

## Decisão

A postura operacional do AION é uma interseção fail-closed de:
- SLO;
- circuit breaker;
- watchdog;
- resource budget;
- bulkhead;
- rate limit;
- backpressure;
- integrity de authority/policy;
- secret posture;
- kill switch;
- backup/restore/journal recovery.

A postura pode recomendar admissão, throttle, read-only ou stop, mas nunca concede
execução.

O Global Kill Switch é independente e domina sinais verdes.

## Consequências

O sistema pode reduzir throughput ou ficar read-only para preservar integridade.
Isso é preferível a propagar falha ou duplicar efeitos externos.

Observabilidade passa a ser requisito de operação e auditoria, não fonte de
permissão.

## Componentes afetados

AION Core, Observability, Resilience, Durable Execution, Global Worker, Journal
Store, Recovery, Incident Center, Policy Kernel e futuros providers.

## Segurança

- deny by default;
- no health-to-authority promotion;
- no SLO-to-approval promotion;
- no automatic rollback;
- no automatic restore;
- no automatic kill-switch mutation;
- bulkhead/rate/backpressure não executam tarefa;
- recovery evidence é separada de execution authority.

## Compatibilidade

Reaproveita os módulos existentes. V2.16 adiciona apenas composição operacional e
novos contracts de SLO/admission.

## Rollback/migração

Remover qualquer sinal obrigatório ou permitir execução por postura operacional
exige ADR sucessor e nova certificação.

## PR/commit relacionado

Branch `integration/aion-v216-operational-resilience-kernel-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
