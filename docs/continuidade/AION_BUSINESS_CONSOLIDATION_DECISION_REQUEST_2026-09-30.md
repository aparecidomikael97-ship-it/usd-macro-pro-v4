# BUSINESS Consolidation Decision Request V1 — 2026-09-30

## Missão

Preparar, sem executar, o objeto administrativo que uma futura decisão humana
precisará referenciar para consolidar a stack #394–#412.

## Bindings obrigatórios

- repositório;
- SHA candidato;
- SHA-base;
- digest do bundle;
- referência da revalidação ao vivo;
- revisor;
- escopo exato.

## Regra anti-drift

O pedido gera um digest canônico. Se SHA, base, bundle, repo, referência de
evidência ou escopo mudarem, o binding falha e uma decisão anterior não pode ser
reaproveitada.

## Estado máximo

`HUMAN_AUTHORIZATION_RECORD_REQUIRED`.

Não equivale a autorização.

## Segurança

Sem merge, rebase, auto-merge, deploy, piloto, runtime, cliente real,
publicação ou cobrança.
