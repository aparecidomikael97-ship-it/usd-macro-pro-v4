# ADR-0040 — Ativação de runtime Business exige escopo limitado e revisão separada

- Título: Ativação de runtime Business exige escopo limitado e revisão separada
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0039 termina em uma fronteira administrativa depois de um deploy verificado.
Ainda faltava definir o contrato que separa a decisão explícita de runtime da
execução física da ativação.

## Problema

Sem uma camada própria de prontidão, uma autorização de runtime poderia ser
interpretada de forma ampla demais, atingir clientes não pretendidos, ignorar
privacidade/suporte/custos ou permitir expansão automática.

## Decisão

Criar um contrato fail-closed de ativação com quatro estágios:

1. requisitos de autorização explícita;
2. preflight com deploy verificado, escopo limitado e guardrails;
3. registro de autorização humana com token exato;
4. packet separado de revisão de execução e template pós-ativação.

Escopos permitidos:

- sandbox: nenhum tenant real;
- pilot: 1 a 10 tenants explicitamente listados;
- bounded_production: 1 a 10 tenants explicitamente listados.

O preflight exige monitoramento, rollback, privacidade, suporte, guardrails
financeiros e saúde das integrações.

O token exato é AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION.

Mensagens genéricas nunca autorizam runtime.

## Consequências

A autorização fica vinculada a um escopo pequeno e auditável. Mesmo uma
autorização válida não autoriza a execução física nem expansão automática.

## Segurança

O módulo não ativa runtime, não altera feature flags, não muda tráfego, não
publica, não cobra e não contata clientes.

## Compatibilidade

ADR-0039 fornece o runtime_boundary_packet. Este ADR consome apenas esse packet
verificado e continua mantendo execução física em outra fronteira.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
