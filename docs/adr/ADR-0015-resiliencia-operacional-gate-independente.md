# ADR-0015 — Resiliência operacional é um gate independente e nunca autoridade

- Título: Resiliência operacional é um gate independente e nunca autoridade
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION possui componentes separados para observabilidade, journal, durable execution,
worker supervision, recovery e segurança. Sem um contrato canônico de postura,
cada consumidor poderia interpretar saúde operacional de maneira diferente.

## Problema

Health, baixa latência ou recovery readiness podem ser confundidos com permissão para
executar. Além disso, falhas de dependência podem propagar em cascata se circuit
breaker, backpressure e kill switch não forem considerados em conjunto.

## Alternativas consideradas

Foram rejeitados:
- health == authority;
- health == approval;
- circuit breaker apenas em prompt;
- retry sem backpressure;
- recovery readiness sem evidência;
- fail-open quando métricas estão ausentes ou inválidas.

## Decisão

O AION adota um Resilience Kernel separado de authority, approval e execution.

A postura canônica é:
- HEALTHY;
- DEGRADED;
- BLOCKED.

O kernel compõe:
- SLOs de latência/erro/saturação;
- pressão de fila/retry backlog;
- circuit breakers;
- journal/audit/checkpoint integrity;
- backup/restore/replay/crash recovery evidence;
- runtime health;
- global kill switch.

Mesmo HEALTHY não concede execução.

## Consequências

O Execution Plane futuro precisa compor Resilience com Authority, Capability,
Approval, Policy Kernel e runtime state. Nenhum desses gates substitui os demais.

## Componentes afetados

AION Core, observability, journal, durable execution, Global Worker, Incident Center,
Recovery, future Policy Kernel e Execution Plane.

## Segurança

- deny by default;
- malformed metrics são rejeitadas;
- open circuit bloqueia;
- hard saturation bloqueia;
- soft limits degradam;
- kill switch ativo bloqueia;
- recovery não verificado bloqueia;
- payload não fabrica execution_allowed.

## Compatibilidade

Preserva V2.13 authority, V2.14 durable execution e V2.15 capability isolation.

## Rollback/migração

Relaxar hard limits, remover recovery evidence ou permitir health implicar execução
exige ADR sucessor e nova certificação.

## PR/commit relacionado

Branch `integration/aion-v216-observability-resilience-recovery-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
