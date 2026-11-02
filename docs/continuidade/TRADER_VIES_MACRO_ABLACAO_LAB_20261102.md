# AtlasQuant Trader — Ablation D1: força FX x veto macro (somente LAB)

Data: 02/11/2026 · revisão draft #1803 · HARD NO-GO

## Questão principal

Uma macroeconomia observada *antes da previsão* faz o viés diário
ser mais útil do que usar apenas a força relativa das moedas?

Para investigar isso sem maquiar assertividade, duas versões devem
ser comparadas no MESMO período, com os MESMOS preços posteriores,
horários e divisão treino/teste. A taxa de acerto deve ser mostrada
junto da cobertura: quantas vezes cada versão realmente previu
ALTA/BAIXA versus AGUARDAR/NEUTRO.

## O que foi programado

- atlasquant_trader_bias_macro_ablation_lab.py reutiliza o
  atlasquant_trader_bias_daily_freeze_lab.py e o avaliador
  atlasquant_trader_bias_oos_lab.py. Não duplica o motor original.
- O baseline usa os 84 vieses sintéticos congelados por dia
  (28 pares x D1/W1/MN1), sem alteração.
- A versão experimental só pode impor um **VETO MACRO AO VIÉS D1**:
  de ALTA/BAIXA para AGUARDAR. Ela não inverte direção,
  não muda W1/MN1 e não define entradas/saídas.
- Cada veto deve ser explicitamente descrito e decidido no
  mesmo horário do baseline, com IDs de evidências macro
  *reais dentro da simulação* já divulgadas/capturadas antes
  do corte. A evidência precisa indicar moeda integrante do
  par e ter origem registrada.
- Eventos futuros só podem constar como agenda, não como
  dados realizados. Um veto que cita evento ainda não
  divulgado, moeda sem relação, campo de resultado futuro
  ou horário posterior é recusado.
- O avaliador OOS recebe DUAS séries de hipóteses e uma
  ÚNICA série de preços futuros, com os mesmos IDs,
  mesmo recorte temporal e mesmas janelas por horizonte.
  Duplicações, períodos sem fechamento, amostras ausentes
  e rótulos futuros rejeitam o experimento inteiro.
- Cada par/horizonte informa cobertura e acertos observados.
  Taxas com amostras insuficientes são omitidas. Os
  28 pares não são considerados estatisticamente independentes.
- Quando a macro apenas veta sinais, os vieses MANTIDOS são
  idênticos aos do baseline. Logo, a precisão em observações
  mantidas é necessariamente igual para os dois métodos;
  uma melhora aparente na taxa total indica **seleção
  de amostras / menor cobertura**, não maior capacidade
  de prever direção. O relatório explicita isso.
- 21 testes sintéticos novos no
  test_atlasquant_trader_bias_macro_ablation_lab.py,
  incorporados à suíte CI Quality.

## O que NÃO foi demonstrado

A evidência de inflação/juros nos testes é inventada como
fixture deliberada. Os vetos também foram escolhidos pelo
teste e NÃO há prova de que uma regra macro feita antes do
mercado teria antecipado esses movimentos.

O modelo não determina automaticamente se CPI alto fortalece
ou enfraquece USD: a reação depende das expectativas de juros,
do consenso anterior, risco e contexto. Não devemos adotar
uma fórmula arbitrária de "macro favorável/desfavorável"
sem especificação e validação. Esta etapa testa somente
a consistência do processo de comparação.

As saídas são LAB_SYNTHETIC_PAIRED_ABLATION,
real_point_in_time_proven=False,
actual_macro_effect_proven=False,
accuracy_improvement_proven=False,
profitability_proven=False,
trade_authorized=False e scheduler_enabled=False.

## Próxima prova para viés realmente assertivo

1. Fonte histórica autorizada e verificável de taxas/fechamentos
   dos 28 pares e de notícias macro com cronologia auditada.
2. Congelamento imutável de previsões ANTES do resultado,
   com definição de regra macro, moeda, contexto e invalidação.
3. Comparação OOS/walk-forward com baseline, filtro e, se
   justificável, versão direcional independente. Medir cobertura,
   acertos, períodos neutros e vieses conflitantes.
4. Exibir primeiro viés diário e explicação do motivo, depois
   semanal (confirmação) e mensal (contexto). Não replicar
   entradas FVG/OB do script TradingView.

**Nenhum** preço real consumido, API consultada, serviço pago,
cron, Worker, deploy, merge, backtest real ou ordem autorizada.
