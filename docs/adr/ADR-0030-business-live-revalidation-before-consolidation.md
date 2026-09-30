# ADR-0030 — Revalidação ao vivo precede qualquer decisão de consolidação Business

- Título: Revalidação ao vivo precede qualquer decisão de consolidação Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A consolidação V2 congela a stack completa AION Core + BUSINESS #394–#412.
Esse snapshot é útil para revisão, mas não pode ser tratado como prova ao vivo
no momento de uma futura decisão de merge.

## Problema

Entre o snapshot e uma decisão administrativa podem ocorrer drift de SHA,
mudança de base, alteração de Draft/open, perda de mergeability, regressão de CI
ou mudança da postura de runtime.

## Decisão

Adicionar um runbook read-only que exija revalidação externa e ao vivo antes de
qualquer decisão administrativa. Os gates mínimos são identidade do repositório,
open/Draft, SHAs, bases, mergeability, checks obrigatórios, UI/mobile, BUSINESS
runtime OFF e ausência de autoridade de merge registrada.

Mesmo com todos os gates, o estado máximo automático é
`READY_FOR_EXPLICIT_ADMIN_DECISION`.

## Stop conditions

Qualquer drift, check não verde, mergeability falsa/desconhecida, mudança de
ordem, runtime diferente de OFF ou ausência de autorização explícita interrompe
a sequência.

## Pós-etapa

Uma futura execução, somente se separadamente autorizada, deve revalidar o SHA
alvo, rodar CI novamente, reconfirmar runtime OFF e preservar o SHA anterior da
main antes de considerar a próxima PR.

## Segurança

O runbook não chama GitHub, não faz merge, rebase, auto-merge, deploy, piloto,
publicação, cobrança ou ativação de runtime.

## Compatibilidade

ADR-0029 continua válido: stack verde não concede autoridade de merge. Este ADR
acrescenta revalidação ao vivo e stop conditions por etapa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
