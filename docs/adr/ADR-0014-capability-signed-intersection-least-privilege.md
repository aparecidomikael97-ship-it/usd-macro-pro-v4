# ADR-0014 — Capability efetiva é interseção assinada de menor privilégio

- Título: Capability efetiva é interseção assinada de menor privilégio
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION possui múltiplos domínios, tenants, workspaces, agentes, ferramentas e níveis de
risco. O V2.13 introduziu autoridade criptográfica real, mas uma authority genérica não
deve virar permissão ampla de execução.

## Problema

Se um agente puder transformar uma authority genérica em qualquer capability,
ferramenta, ação, tenant ou domínio, o sistema fica vulnerável a privilege escalation
mesmo com assinatura válida.

## Alternativas consideradas

Foram rejeitados:
- confiar em role declarada pelo agente;
- confiar apenas em capability metadata;
- usar um allow-all após authority válida;
- permitir tool/action não assinada;
- permitir scope cross-domain implícito;
- usar memória como fonte de permissão.

## Decisão

Cada capability operacional exige um Capability Scope Grant assinado e vinculado ao
parent authority statement.

A capability efetiva é a interseção entre parent authority, Capability Registry,
Specialist Router/domain profile, actor role, tool/action ceilings, tenant/workspace/
domain namespace e cost ceiling.

Nenhum componente isolado pode ampliar a interseção.

## Consequências

Uma assinatura válida que peça capability fora do domínio ou tool/action não declarada
continua BLOCKED. O grant pode reduzir autoridade, nunca ampliá-la.

## Componentes afetados

Control Plane, Capability Registry, Specialist Router, Tenant Isolation, Tool Hub,
Role Authority, Durable Execution e futuro Policy Kernel.

## Segurança

- least privilege;
- deny by default;
- tenant/domain/workspace isolation;
- no agent self-grant;
- no memory-derived permission;
- signed budget ceiling;
- tool/action ceiling;
- execution remains a downstream gate.

## Compatibilidade

Preserva os contratos existentes. V2.15 não ativa specialist runtime nem provider.

## Rollback/migração

Relaxar qualquer ceiling exige novo ADR e nova certificação.

## PR/commit relacionado

Branch `integration/aion-v215-capability-isolation-binding-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
