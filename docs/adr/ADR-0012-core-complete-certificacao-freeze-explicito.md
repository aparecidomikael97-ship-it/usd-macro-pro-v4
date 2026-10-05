# ADR-0012 — Núcleo só conclui após certificação integral e Core Freeze explícito

- Título: Núcleo só conclui após certificação integral e Core Freeze explícito
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O V2.12 fechou sua camada intermediária com CI verde, mas o proprietário determinou
que o núcleo não deve ser congelado ou declarado concluído enquanto existirem
pendências estruturais conhecidas.

## Problema

Confundir uma versão intermediária verde com núcleo completo criaria dívida técnica e
obrigaria refatoração estrutural posterior.

## Alternativas consideradas

Foi rejeitado congelar o núcleo após V2.12 ou após qualquer gate isolado. Também foi
rejeitado empurrar conscientemente trust, durable execution, isolation, resilience,
memory governance, policy kernel ou provider independence para uma fase indefinida.

## Decisão

O AION Core permanece em desenvolvimento estrutural até completar ou resolver por
contrato equivalente a sequência canônica V2.13–V2.20:

- real trust root/authority;
- durable execution;
- isolation/capability security;
- observability/resilience/recovery;
- multi-agent governor/memory governance;
- Constitution/Policy Kernel;
- model gateway/provider independence;
- core certification end-to-end/red-team/load/chaos/recovery.

CI verde intermediário não significa Core Complete.

## Consequências

O Core Freeze só pode ocorrer após certificação integral e autorização explícita do
proprietário. Após o freeze, novas capacidades devem preferencialmente entrar por
adapters/plugins preservando contratos centrais.

## Componentes afetados

Todo AION Core, ADR registry, Checkpoint Mestre, CI, worker, memory, capabilities,
tenants e providers.

## Segurança

Nenhum atalho pode converter readiness em authority; memória não concede permissão;
health não implica approval; approval não implica automaticamente execução.

## Compatibilidade

Este ADR complementa ADR-0006, ADR-0007, ADR-0008, ADR-0009 e ADR-0010.

## Rollback/migração

Relaxar o critério exige ADR posterior explícito e nova certificação.

## PR/commit relacionado

Checkpoint canônico da PR #607 e sequência estrutural V2.13–V2.20.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
