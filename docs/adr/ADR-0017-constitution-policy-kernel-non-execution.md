# ADR-0017 — Constituição AION vive em código e Policy Kernel nunca executa

- Título: Constituição AION vive em código e Policy Kernel nunca executa
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION combina modelos, agentes, memória, ferramentas, tenants e domínios. Regras
críticas mantidas apenas em prompt podem ser alteradas por contexto, erro de modelo ou
injeção.

## Problema

Sem um kernel de política determinístico, sinais corretos de authority, health,
approval ou memory podem ser compostos de forma inconsistente e criar privilege
escalation.

## Alternativas consideradas

Foram rejeitados:
- constituição em prompt;
- policy definida por memória;
- action allowlist fornecida pelo caller;
- health green como execução;
- owner approval como execução;
- kill switch controlado pelo agente;
- auto-deploy/auto-merge dentro do kernel.

## Decisão

A Constituição AION é um manifesto canônico, versionado em código, com digest
determinístico.

O Policy Kernel:
- reconhece somente ações canônicas;
- compõe authority, capability, operational posture, multi-agent governance,
  durable execution, approval, cost, privacy e kill switch;
- nunca executa;
- nunca retorna execution_allowed=True;
- nunca muda a própria constituição em runtime.

Mudança de política é review-only e exige processo posterior explícito.

## Consequências

Modelos e agentes podem evoluir sem alterar as regras invioláveis.

Uma decisão `POLICY_PERMITS_PROGRESS` significa somente que a intenção pode chegar
ao próximo gate. Não significa execução.

## Componentes afetados

AION Core, Control Plane, Execution Plane, Authority, Capability Isolation,
Operational Resilience, Multi-Agent Governor, Memory Governance, Approval, Cost,
Tenant Privacy, Worker e future Execution Gate.

## Segurança

- policy tamper fail-closed;
- unknown action deny-by-default;
- owner approval bound to policy digest + action + tenant + domain;
- kill switch dominates sensitive actions;
- cost ceilings cannot expand;
- privacy review required for tenant deletion;
- real-trading flag is separate;
- memory/health never grant authority;
- policy kernel never executes.

## Compatibilidade

Compõe V2.13–V2.17 sem substituir os contratos existentes.

## Rollback/migração

Alterar qualquer invariant ou action rule exige ADR sucessor e nova certificação.

## PR/commit relacionado

Branch `integration/aion-v218-constitution-policy-kernel-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
