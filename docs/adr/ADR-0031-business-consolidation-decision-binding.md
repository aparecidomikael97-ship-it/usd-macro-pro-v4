# ADR-0031 — Decisão de consolidação deve ser vinculada a SHA e digest exatos

- Título: Decisão de consolidação deve ser vinculada a SHA e digest exatos
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A stack #394–#412 possui consolidação congelada e dry-run com revalidação ao
vivo. Ainda faltava impedir que uma futura autorização humana genérica fosse
reaproveitada depois de mudança de código, base ou evidência.

## Problema

Frases genéricas de aprovação, registros sem SHA ou decisões ligadas somente ao
número de uma PR podem sobreviver a drift de branch, novo commit, alteração do
bundle ou substituição da evidência de CI.

## Decisão

Criar um pedido de decisão administrativo não executável, vinculado a:

- repositório exato;
- SHA candidato;
- SHA-base;
- digest congelado da stack;
- referência da evidência ao vivo;
- escopo `STACK_CONSOLIDATION_394_412_ONLY`;
- revisor identificado.

O pedido recebe um digest próprio. Qualquer drift em um dos bindings invalida o
pedido e exige nova revisão.

## Estado máximo

`HUMAN_AUTHORIZATION_RECORD_REQUIRED`.

Esse estado significa apenas que existe material suficiente para uma decisão
humana explícita. Não registra autorização.

## Segurança

O módulo nunca faz merge, rebase, auto-merge, deploy, piloto, publicação,
cobrança ou ativação de runtime. Também não interpreta mensagens genéricas como
autorização.

## Compatibilidade

ADR-0029 mantém a separação entre CI verde e autoridade. ADR-0030 mantém a
revalidação ao vivo. Este ADR adiciona binding criptográfico da futura decisão.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
