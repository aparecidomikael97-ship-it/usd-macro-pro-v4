# ADR-0033 — Execução de consolidação exige preflight separado e sequencial

- Título: Execução de consolidação exige preflight separado e sequencial
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A stack Business já possui snapshot, revalidação ao vivo, pedido de decisão
vinculado e contrato de autorização explícita. Faltava uma última fronteira
antes de qualquer ação física no repositório.

## Problema

Mesmo uma autorização explícita pode ficar obsoleta se a main mudar, se a ordem
da stack for pulada, se o runtime deixar de estar OFF ou se surgir autoridade de
deploy.

## Decisão

Criar um preflight read-only por etapa. Ele exige:

- dry-run pronto;
- decision request vinculado;
- authorization record explícito verificado;
- live revalidation atual;
- lista de PRs concluídas como prefixo exato da stack;
- alvo igual à próxima PR da sequência;
- SHA observado da main igual ao esperado;
- BUSINESS runtime OFF;
- ausência de autoridade de deploy.

## Estado máximo

`MERGE_EXECUTION_REVIEW_REQUIRED`.

Mesmo nesse estado, `merge_execution_authorized=false` e
`executes_action=false`.

## Pós-etapa

Após qualquer merge futuro separadamente executado, antes de considerar a
próxima PR deve-se verificar o SHA resultante, rodar CI completo, revalidar
UI/mobile quando aplicável, confirmar runtime OFF, preservar o SHA anterior para
rollback e interromper em qualquer drift.

## Segurança

O módulo não chama GitHub, não mergeia, não rebaseia, não habilita auto-merge,
não deploya, não autoriza piloto e não ativa runtime.

## Compatibilidade

ADR-0030 define revalidação ao vivo; ADR-0031 vincula a decisão; ADR-0032 define
a autorização explícita. Este ADR separa tudo isso da execução física e impõe
ordem sequencial fail-closed.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
