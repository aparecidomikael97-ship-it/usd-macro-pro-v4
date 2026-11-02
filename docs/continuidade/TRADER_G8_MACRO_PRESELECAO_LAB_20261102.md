# AtlasQuant Trader — Pré-seleção macro G8/28 pares (somente LAB)

Data: 02/11/2026 • PR #1803 DRAFT • HARD NO-GO

## Objetivo

Evitar otimização retrospectiva da macroeconomia no backtest do
viés diário. A escolha do indicador deve anteceder o período
em que o desempenho será avaliado, e não ser feita depois
que os retornos de EUR/USD, USD/JPY ou outro par já ficaram
conhecidos.

A matriz macro anterior usa oito moedas e quatro grupos:
inflação, emprego, política de juros e atividade. Esta entrega
acrescenta um **plano experimental pré-definido de 32 escolhas**,
sem inventar um ranking da força econômica das moedas.

## Novo contrato

Arquivo: atlasquant_trader_g8_macro_selection_lab.py.

1. O pesquisador prepara um documento LAB_SYNTHETIC_G8_MACRO_POLICY
   com ID, versão de método, horário de registro, início do
   período experimental e 32 escolhas exclusivas.
2. Cada escolha tem moeda G8, grupo econômico, indicador,
   unidade e justificativa. A escolha deve pertencer ao grupo:
   CPI/Core CPI/PCE para inflação; NFP/ADP/desemprego/salários
   para emprego; POLICY_RATE para juros; PIB/PMI/ISM para
   atividade. Esses são exemplos aceitos, NÃO recomendações
   oficiais para cada país.
3. freeze_g8_macro_indicator_policy_lab calcula um SHA-256 de
   conteúdo SOMENTE se o relógio sintético da pesquisa ainda
   for anterior ao início do período experimental.
4. compare_preselected_g8_macro_lab verifica o conteúdo
   congelado, o SHA e se cada evento apresentado corresponde
   EXATAMENTE ao indicador e unidade escolhidos. Não há
   substituição silenciosa, nem "melhor indicador" escolhido
   depois do preço, nem segunda leitura do mesmo grupo para
   a mesma moeda.
5. Para indicador selecionado sem informação recebida, a
   matriz mostra SELECTED_INDICATOR_NOT_REPORTED. Para dados
   liberados ou agendados usa os estados já existentes
   (RELEASED_BEFORE_CUTOFF, SCHEDULED_NOT_RELEASED,
   STALE_RELEASE) do módulo de comparação macro.
6. A saída inclui pares canônicos, evidências sintéticas,
   cobertura e lacunas, com **macro_direction UNDETERMINED**,
   nenhuma pontuação/ordem/veto automático. Mantém D1
   prioritário, W1 confirmação e MN1 contexto.
7. O experimento não serve para identificar por conta própria
   qual indicador é mais importante para cada banco central:
   isso exige estudo de expectativas, regime e divulgação
   histórica ponto-no-tempo.

O SHA é apenas um identificador determinístico. O usuário
ainda poderia fabricar um documento e um horário de registro
retroativamente; **não existe custódia, carimbo independente
nem prova histórica nesta etapa**.

## Testes

test_atlasquant_trader_g8_macro_selection_lab.py:
29 testes de contrato e integração, adicionados à Quality CI.
Cobrem 32 escolhas únicas, invariância de ordem, alteração do
plano ou justificativa, relógios antes/depois do experimento,
ausência do indicador escolhido, recusa de substituição de
CPI por Core CPI, unidade diferente, resultado macro futuro,
agenda sem valor realizado, proteção contra duplicatas,
ausência de fonte e não-habilitação de trades.

## Critério para evoluir

Antes de decidir quais 32 indicadores usar de verdade:
- Documentar cobertura e convenções nacionais, fonte, idioma,
  calendário, revisão de dados e expectativas publicadas;
- Pré-registrar política, janela treino/holdout e regra
  de alteração ANTES do teste;
- Comprovar histórico de consensos/vintages e fonte spot
  para os 28 pares, respeitando licenciamento e custo;
- Executar comparação OOS entre força relativa simples e
  macro como contexto/filtro, avaliando simultaneamente
  assertividade, cobertura e dependência temporal;
- Exigir verificação independente antes de comunicar
  assertividade real ao proprietário ou clientes.

**Nenhuma API** foi consultada, nenhum dado de preço real
ingressou e nenhuma chamada paga, operação, Worker, cron,
merge ou deploy foi autorizada. PR DRAFT / HARD NO-GO.
