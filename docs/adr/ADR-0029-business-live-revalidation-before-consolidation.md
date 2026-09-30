# ADR-0029 — Revalidação ao vivo precede qualquer decisão de consolidação Business

- Título: Revalidação ao vivo precede qualquer decisão de consolidação Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A Draft PR #413 consolidou um snapshot técnico da stack Business #398–#411.
Esse snapshot é útil para revisão, mas não pode ser tratado como prova ao vivo no
momento de uma futura decisão de merge.

## Problema

Entre a captura de um snapshot e uma decisão administrativa, podem ocorrer drift
de SHA, mudança de base, alteração de Draft/open, perda de mergeability ou
mudança de CI. Uma sequência baseada apenas em evidência congelada pode ficar
obsoleta sem aviso.

## Decisão

Adicionar um runbook read-only de consolidação que exija revalidação externa e
ao vivo antes de qualquer decisão administrativa.

Os gates mínimos são:

- identidade do repositório;
- todas as PRs abertas;
- todas as PRs ainda Draft;
- SHAs intactos;
- bases intactas;
- mergeability verdadeira;
- checks obrigatórios verdes;
- checks UI/mobile verdes quando aplicáveis.

Mesmo com todos os gates, o estado máximo automático é
`READY_FOR_EXPLICIT_ADMIN_DECISION`.

## Stop conditions

Qualquer drift, check não verde, mergeability falsa/desconhecida, alteração de
ordem ou ausência de autorização explícita interrompe a sequência.

## Segurança

O runbook não chama GitHub, não faz merge, rebase, auto-merge, deploy ou
ativação de runtime. Ele não altera cliente, provider, credencial ou cobrança.

## Pós-etapa

Uma futura execução, caso separadamente autorizada, deve revalidar o resultado e
rodar CI novamente antes de considerar a próxima PR. Ao final, CI da main e
verificação do SHA de produção continuam obrigatórios e separados.

## Compatibilidade

ADR-0028 continua válido: stack verde não concede autoridade de merge. Este ADR
acrescenta a exigência de evidência ao vivo imediatamente antes da decisão.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
