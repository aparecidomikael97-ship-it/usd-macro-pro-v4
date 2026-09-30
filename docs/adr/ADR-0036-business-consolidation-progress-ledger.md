# ADR-0036 — Progresso da consolidação é um ledger sequencial de recibos verificados

- Título: Progresso da consolidação é um ledger sequencial de recibos verificados
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0035 valida cada etapa após um futuro merge. Faltava consolidar essas
validações em um estado sequencial que impeça saltos, duplicações ou recibos
desconectados.

## Decisão

Criar um ledger offline e read-only para a stack #394–#412.

Cada entrada precisa ser um resultado
`STEP_VERIFIED_FOR_NEXT_PREFLIGHT` válido e deve:

- corresponder exatamente à próxima PR canônica;
- ter receipt digest único;
- ter main SHA resultante único;
- usar como rollback reference exatamente o main SHA da etapa anterior;
- manter `executes_action=false`.

A primeira etapa ancora no `root_main_sha` informado externamente.

## Estados

- `ROOT_MAIN_SHA_REQUIRED`: template sem âncora;
- `READY_FOR_FIRST_PREFLIGHT`: nenhum merge verificado ainda;
- `READY_FOR_NEXT_PREFLIGHT`: prefixo válido parcial;
- `LEDGER_BLOCKED`: salto, duplicação ou quebra da cadeia;
- `CONSOLIDATION_COMPLETE_REVIEW_REQUIRED`: as 19 etapas foram verificadas.

## Finalização

Mesmo com as 19 etapas verificadas, o máximo é revisão humana final.
Deploy, produção e runtime continuam separados.

## Segurança

Sem GitHub/network action, merge, rollback, rebase, auto-merge, deploy,
publicação, cobrança, piloto ou ativação de runtime.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
