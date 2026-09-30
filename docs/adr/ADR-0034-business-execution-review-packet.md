# ADR-0034 — Revisão humana de execução usa pacote congelado e digestado

- Título: Revisão humana de execução usa pacote congelado e digestado
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0033 introduziu o preflight read-only imediatamente anterior à fronteira de
merge. Ainda faltava uma forma de apresentar a evidência ao administrador sem
misturar revisão com execução.

## Decisão

Criar um pacote de revisão de execução imutável e digestado a partir de um
preflight válido. O pacote liga target PR, target SHA, base SHA, main pré-merge,
rollback SHA, request digest, referência de evidência e revisor.

## Estado máximo

`READY_FOR_HUMAN_EXECUTION_REVIEW`.

Esse estado significa apenas que o dossiê está íntegro para leitura humana.
Ele não cria autorização e mantém `merge_execution_authorized=false`.

## Anti-drift

Alteração de target SHA, rollback SHA ou digest do próprio pacote gera
`PACKET_BINDING_MISMATCH` e exige reconstrução do dossiê.

## Segurança

Sem GitHub/network action, merge, rebase, auto-merge, deploy, piloto, publicação,
cobrança, cliente real ou runtime.

## Compatibilidade

ADR-0033 continua sendo o preflight sequencial. Este ADR apenas congela sua
evidência para revisão humana separada.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
