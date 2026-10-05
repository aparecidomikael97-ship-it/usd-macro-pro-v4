# ADR-0016 — Supervisor coordena sem autoridade própria e memória nunca concede permissão

- Título: Supervisor coordena sem autoridade própria e memória nunca concede permissão
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION possui um núcleo orquestrador, agentes especializados e múltiplas camadas de
memória. À medida que o ecossistema cresce, coordenação e memória podem se tornar
fontes indiretas de privilege escalation se não houver uma fronteira explícita.

## Problema

Dois atalhos são perigosos:

1. assumir que o supervisor pode ampliar a própria autoridade só porque coordena
   outros agentes;
2. assumir que uma memória validada pode conceder capability, approval ou execução.

Também é necessário impedir delegação infinita, custos sem limite e memória vencida
ou fora de tenant/persona sendo reutilizada.

## Alternativas consideradas

Foram rejeitados:
- supervisor como root authority;
- agente filho herdando tudo implicitamente;
- capability solicitada fora de teto;
- delegação sem lineage;
- loops sem depth/fan-out limits;
- memória validada sem TTL/confidence/scope;
- apagar memória expirada e perder auditoria;
- metadata de memória capaz de definir execution_allowed.

## Decisão

O supervisor é um coordenador canônico, não uma raiz de confiança.

Todo plano multiagente deve ser limitado por:
- supervisor root binding;
- delegation lineage;
- depth/fan-out/node ceilings;
- capability request ceiling;
- deadline;
- call/token/wall/memory budget;
- cost budget.

Memória operacional deve passar por governança de:
- validation/provenance;
- tenant/persona scope;
- confidence;
- validity/TTL;
- retention;
- conflict/tombstone state.

Memória expirada é removida do uso operacional por tombstone versionado, preservando
histórico.

## Consequências

Um plano pode estar dentro dos limites sem receber execução. Uma memória pode ser
USABLE sem conceder qualquer permissão.

Execution authority continua sendo composta em gates posteriores.

## Componentes afetados

AION Core, Orchestrator, Loop Governor, Specialist agents, Capability Isolation,
Memory Contract, Memory Architecture, Checkpoint, Audit, future Policy Kernel.

## Segurança

- no supervisor self-grant;
- no child implicit privilege escalation;
- no infinite delegation;
- no memory-derived authority;
- no cross-tenant/persona read;
- no expired memory as operational truth;
- audit history preserved through tombstones;
- legal hold cannot be expiry-deleted.

## Compatibilidade

O V2.17 envolve contratos existentes em vez de substituí-los.

## Rollback/migração

Relaxar qualquer ceiling ou permitir memória conceder permissão exige ADR sucessor e
nova certificação.

## PR/commit relacionado

Branch `integration/aion-v217-multiagent-memory-governance-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
