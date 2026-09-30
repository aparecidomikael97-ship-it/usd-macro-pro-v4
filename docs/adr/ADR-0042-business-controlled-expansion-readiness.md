# ADR-0042 — Expansão Business exige progressão limitada e nova autorização explícita

- Título: Expansão Business exige progressão limitada e nova autorização explícita
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0041 congela o escopo depois de uma ativação verificada e abre somente uma
fronteira administrativa para eventual expansão.

## Problema

Sem um preflight próprio, a expansão poderia saltar etapas, remover tenants já
autorizados, exceder capacidade, ou reutilizar uma autorização antiga para um
escopo diferente.

## Decisão

Criar um contrato fail-closed de prontidão para expansão.

Regras principais:

1. sandbox só pode promover para pilot;
2. pilot pode ganhar tenants dentro do limite ou promover para bounded_production;
3. bounded_production é o estágio terminal desta versão e só pode ampliar tenants dentro do limite;
4. tenants existentes precisam ser preservados;
5. no máximo 10 tenants por escopo limitado;
6. privacidade, suporte, finanças, integrações, capacidade, monitoramento e rollback precisam ser revalidados;
7. toda autorização é vinculada ao preflight exato;
8. autorização não é execução.

O token exato é AUTHORIZE_BUSINESS_SCOPE_EXPANSION.

## Consequências

A expansão se torna incremental, auditável e reversível por revisão. Nenhuma
mensagem genérica libera crescimento.

## Segurança

O módulo não altera runtime, tenants, tráfego, deploy, rollback, cobrança,
publicação ou comunicação com clientes.

## Compatibilidade

ADR-0041 fornece o expansion boundary packet. Este ADR apenas valida uma proposta
de expansão e prepara uma revisão de execução separada.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
