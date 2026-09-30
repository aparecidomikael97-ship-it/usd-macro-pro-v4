# ADR-0062 — Oportunidades de receita usam custo e capacidade reais sem automatizar preço ou venda

Título: Oportunidades de receita usam custo e capacidade reais sem automatizar preço ou venda  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O Revenue Opportunity Engine já prioriza serviços B2B com gates de orçamento,
margem e capacidade. Porém, custo mensal e capacidade ainda podiam chegar como
inputs manuais.

## Problema

Um ranking comercial pode parecer melhor do que a realidade se custo e capacidade
forem estimados sem vínculo com o FinOps e com o Capacity Manager.

## Alternativas consideradas

1. Manter custo e capacidade como inputs manuais.
2. Criar um novo ranking separado.
3. Vincular o engine existente ao ledger FinOps verificado e ao Capacity Manager
   com métricas reais.

## Decisão

Adotar a alternativa 3.

O binding:
- verifica o ledger FinOps;
- exige alocações explícitas por entry_id;
- deriva o custo mensal por oportunidade;
- exige `LIVE_CAPACITY_REVIEW_READY`;
- injeta somente `estimated_monthly_cost_brl` e `capacity_ready` no engine já
  existente;
- mantém preço, startup budget, prazo e scores qualitativos como inputs
  administrativos explícitos.

Percentuais de alocação:
- são inputs administrativos;
- ficam ligados ao digest do ledger;
- não alteram o ledger;
- não movimentam dinheiro.

## Consequências

O ranking passa a refletir custo e capacidade observados sem criar um segundo
motor e sem transformar score em previsão de venda.

## Segurança

A camada não:
- define preço automaticamente;
- vende;
- entra em contato;
- gasta;
- cobra;
- admite cliente;
- provisiona tenant;
- faz deploy;
- ativa runtime.

## Compatibilidade

Complementa ADR-0060, ADR-0061 e ADR-0058.

## Rollback/migração

Read-only. Remoção não altera ledger, capacidade, preço ou cliente.

## PR/commit relacionado

Draft PR AION BUSINESS Revenue Live Economics Binding V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
