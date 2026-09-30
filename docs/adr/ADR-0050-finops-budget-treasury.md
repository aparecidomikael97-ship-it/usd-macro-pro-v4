# ADR-0050 — FinOps governa orçamento e separa tesouraria por ecossistema

Título: FinOps governa orçamento e separa tesouraria por ecossistema  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O ecossistema AtlasQuant/AION terá três frentes econômicas principais: Negócios,
Trader e Investimentos. O projeto ainda está em fase de construção e precisa
crescer sem comprometer o orçamento pessoal do administrador.

## Problema

Sem uma política central, custos de IA/infraestrutura podem ultrapassar o limite
planejado e o capital gerado por Negócios, Trader e Investimentos pode se misturar
de forma pouco controlada.

## Alternativas consideradas

1. Caixa único sem regras.
2. Limites manuais fora do sistema.
3. FinOps central com teto mensal e buckets lógicos de tesouraria.

## Decisão

Adotar a alternativa 3.

Políticas iniciais:
- teto mensal do ecossistema: R$200;
- receita líquida de Negócios como principal fonte de financiamento do ecossistema;
- lucro líquido do Trader retido no bucket Trader;
- Investimentos com função de construção/preservação patrimonial;
- alocação inicial máxima ao Trader: 30% do capital total do ecossistema;
- metas de retorno de Trade são metas de planejamento, nunca promessa ou retorno esperado;
- nenhuma transferência, gasto ou trade é automático.

## Consequências

O AION pode sinalizar quando o custo se aproxima do teto e pode bloquear planos
que o ultrapassem. O sistema também separa a lógica financeira de cada frente.

## Componentes afetados

- AION Core;
- Business;
- Trader;
- Investments;
- FinOps;
- Central Financeira;
- Checkpoint Mestre.

## Segurança

A política não movimenta dinheiro, não altera billing, não faz trade e não
aumenta orçamento automaticamente. Mudanças de teto ou alocação exigem revisão
administrativa separada.

## Compatibilidade

Compatível com o teto de R$200 já registrado no Checkpoint Mestre e com a
estratégia de Negócios como gerador inicial de caixa.

## Rollback/migração

Módulo read-only. Remoção não movimenta nem altera saldos reais.

## PR/commit relacionado

Draft PR FinOps Budget Governor & Treasury V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
