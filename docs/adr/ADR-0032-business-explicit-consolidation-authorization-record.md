# ADR-0032 — Autorização de consolidação exige registro explícito e vinculado

- Título: Autorização de consolidação exige registro explícito e vinculado
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0031 criou um pedido de decisão vinculado ao SHA, base, bundle e evidência
exatos. Ainda faltava definir como uma eventual autorização humana seria
representada sem transformar linguagem genérica em permissão operacional.

## Problema

Expressões como "ok", "vamos lá", "pode seguir" ou "autorizo" são ambíguas fora
de contexto e não devem liberar uma operação de consolidação de repositório.

## Decisão

Uma autorização válida deve ser um registro explícito ligado ao digest do pedido
e conter:

- token exato `AUTHORIZE_STACK_CONSOLIDATION_394_412`;
- digest exato do pedido;
- escopo `STACK_CONSOLIDATION_394_412_ONLY`;
- aprovador igual ao revisor esperado;
- timestamp de aprovação;
- acknowledgements explícitos de escopo, deploy separado, piloto separado,
  runtime OFF, CI pós-etapa e stop-on-drift.

Qualquer campo ausente, lookalike textual ou digest divergente rejeita o
registro.

## Limite de autoridade

Mesmo um registro validado chega apenas a
`EXPLICIT_AUTHORIZATION_RECORD_VERIFIED`.

O módulo não executa merge. `merge_execution_authorized` permanece `False`
porque execução física é uma fronteira separada e deve revalidar o binding no
momento da ação.

## Segurança

Sem GitHub/network action, auto-merge, deploy, piloto, publicação, cobrança ou
ativação de runtime.

## Compatibilidade

ADR-0029 separa CI de autoridade; ADR-0030 exige revalidação ao vivo; ADR-0031
amarra a decisão ao digest. Este ADR define o formato explícito e anti-ambíguo
da autorização.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
