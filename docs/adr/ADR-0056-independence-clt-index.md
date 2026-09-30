# ADR-0056 — Índice de Independência CLT usa entradas privadas e não toma a decisão de transição

Título: Índice de Independência CLT usa entradas privadas e não toma a decisão de transição  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O ecossistema precisa acompanhar quando a renda gerada fora do emprego passa a
ter consistência suficiente para justificar uma revisão humana da transição.

## Problema

Um único mês forte, renda dependente de Trade ou concentração excessiva em um
cliente não são evidência suficiente para tratar a saída do emprego como segura.

## Alternativas consideradas

1. Usar apenas renda mensal atual.
2. Usar um score/probabilidade de saída.
3. Índice multi-gate com renda não-Trade, consistência, reserva, recorrência e
   concentração, mantendo a decisão final com o usuário.

## Decisão

Adotar a alternativa 3.

O índice considera entradas privadas em runtime:
- faixa de renda líquida-base;
- histórico mensal de renda líquida não-Trade do ecossistema;
- multiplicador de segurança;
- meses mínimos de consistência;
- meses de reserva;
- receita recorrente;
- concentração no maior cliente;
- dependência do Trade para despesas essenciais.

O resultado é uma zona de planejamento, não uma probabilidade.

## Privacidade

Nenhuma renda pessoal é hardcoded ou persistida por este módulo no repositório.
Valores pessoais permanecem como entradas de runtime.

## Segurança

O índice:
- não recomenda pedir demissão;
- não movimenta dinheiro;
- não executa Trade;
- não altera orçamento;
- não grava valores pessoais;
- não toma decisão em nome do usuário.

## Consequências

O AION pode sinalizar BUILDING, APPROACHING ou TRANSITION_REVIEW_ZONE e apresentar
perguntas de revisão, mas a decisão continua humana.

## Compatibilidade

Compatível com FinOps/Tesouraria e com a diretriz de não depender de Trade para
despesas essenciais.

## PR/commit relacionado

Draft PR AION Independence Index V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
