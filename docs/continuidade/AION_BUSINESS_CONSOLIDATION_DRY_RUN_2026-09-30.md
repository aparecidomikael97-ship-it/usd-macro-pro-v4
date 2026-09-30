# BUSINESS Consolidation Dry-Run V1 — 2026-09-30

## Missão

Transformar a consolidação técnica da #413 em um runbook administrativo
fail-closed, sem executar qualquer ação no GitHub.

## Entrada

- snapshot consolidado da stack #398–#411;
- revalidação externa e ao vivo de identidade, estado, SHAs, bases,
  mergeability e CI.

## Estados

- `STACK_REVIEW_BLOCKED`: o snapshot base não está íntegro;
- `AWAITING_LIVE_REVALIDATION`: snapshot íntegro, mas falta prova ao vivo;
- `READY_FOR_EXPLICIT_ADMIN_DECISION`: prova ao vivo completa, ainda sem
  autorização de merge.

## Sequência

O runbook preserva a ordem #398 → #411 e exige, para cada etapa:

1. revalidar SHA/base/Draft/open/mergeability/checks;
2. confirmar autorização administrativa explícita separada;
3. somente então uma execução futura poderia considerar a ação;
4. após qualquer etapa futura, revalidar o alvo e rodar CI antes da próxima.

## Stop conditions

Drift, CI pendente/falho, mudança de base, mergeability desconhecida/falsa,
perda do estado Draft/open, mudança de ordem ou ausência de autorização.

## Segurança

Este bloco:

- não mergeia;
- não rebaseia;
- não habilita auto-merge;
- não deploya;
- não liga BUSINESS runtime;
- não toca cliente real;
- não publica;
- não cobra.

## Estado atual

A #413 está verde, mas isso apenas permite preparar este runbook. A autoridade
continua humana e separada.
