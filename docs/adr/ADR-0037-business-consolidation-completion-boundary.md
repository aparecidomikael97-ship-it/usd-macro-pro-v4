# ADR-0037 — Consolidação técnica completa não equivale a deploy ou runtime

- Título: Consolidação técnica completa não equivale a deploy ou runtime
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O ledger sequencial da stack Business pode, futuramente, registrar as 19 etapas
#394–#412 como pós-merge verificadas e chegar a
`CONSOLIDATION_COMPLETE_REVIEW_REQUIRED`.

## Problema

Sem uma fronteira final, "todas as etapas verdes" poderia ser interpretado como
autorização para deploy, produção, piloto ou ativação de runtime.

## Decisão

Adicionar uma revisão final independente que exige:

- ledger completo;
- SHA final da main coerente;
- todos os checks finais verdes;
- UI/mobile verdes;
- runtime BUSINESS OFF;
- deploy explicitamente separado;
- evidência final identificável.

O máximo automático é `READY_FOR_FINAL_ADMIN_REVIEW`.

O fechamento técnico exige o token explícito
`ACKNOWLEDGE_BUSINESS_CONSOLIDATION_COMPLETE` e todos os acknowledgements
obrigatórios.

Mesmo após o acknowledgement técnico, deploy e runtime continuam não autorizados.

## Consequências

A cadeia administrativa distingue quatro fatos diferentes:

1. stack tecnicamente consolidada;
2. consolidação tecnicamente reconhecida pelo administrador;
3. deploy aprovado;
4. runtime/produção aprovado.

Nenhum passo implica automaticamente o seguinte.

## Segurança

Mensagens genéricas não são autorização. O módulo não executa ação externa.

## Compatibilidade

ADR-0036 define o ledger sequencial. Este ADR define o gate final depois do
ledger completo.

## Rollback

Módulo read-only; remoção não exige compensação externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
