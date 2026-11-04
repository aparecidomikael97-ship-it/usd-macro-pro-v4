# AtlasQuant Trader — histórico M15 no formato MT5, sem API paga

Data: 04/11/2026. Somente **LAB offline**, para pesquisa e preparação de backtests.
Não pressupõe que o proprietário tenha MetaTrader 5 ou uma conta com os 28 pares.

## Fonte de formato

A integração Python oficial do MetaTrader 5 retorna barras com campos
`time, open, high, low, close, tick_volume, spread, real_volume`.
O tempo das barras é UTC. A barra de índice zero pode estar aberta;
exportadores futuros deverão escolher **somente barras fechadas**.

- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrompos_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py
- https://www.mql5.com/en/docs/constants/structures/mqlrates

**Este código não importa a biblioteca MetaTrader5 e não acessa terminais,
brokers, contas, chaves, HTTP, ordens ou preços atuais.** Recebe exclusivamente
dados sintéticos ou exportações que o chamador já forneceu.

## Contrato e segurança

Módulo `atlasquant_mt5_m15_history_lab.py`,
`analyze_mt5_m15_history(payload, now=...)`.

- `schema=ATLASQUANT_MT5_28_M15_HISTORY_IMPORT_LAB_V1`
- `state=OFFLINE_RESEARCH`, `timeframe=M15`, `terminal_claim` informativo
- Chaves exatas dos 28 pares canônicos G8, sem inversão ou símbolos adicionais
- Por par, 3 a 2.000 barras cronológicas, com tempo Unix em segundos UTC,
  OHLC positivo, tick_volume e spread em números inteiros não negativos
- Barras alinhadas em intervalos de 15 minutos, sem duplicidade, desordem,
  valores NaN/infinitos, candles futuros ou incompletos na data da análise
- A lista exata de timestamps deve ser **idêntica nos 28 pares**. Feriados e
  fins de semana podem formar lacunas, que são contabilizadas, nunca preenchidas
  artificialmente
- Qualquer falha bloqueia toda a coleção, sem emitir ranking parcial

Saída íntegra: `RESEARCH_ONLY`, horários, 28 últimos fechamentos,
`tick_volume` e `spread` em pontos de cada par. As flags de autenticação,
exibição, precisão, bid/ask executável, custo de spread e performance de
backtest ficam sempre **falsas**.

## Interpretação obrigatória

- OHLC de uma barra MT5 **não contém, por si só, os dois lados históricos de
  execução bid/ask**. O campo spread é um número de **pontos**, cuja conversão
  depende do contrato do símbolo e não comprova custo realizável, slippage
  ou qualidade do feed.
- `tick_volume` é contagem de ticks do provedor, não volume consolidado de
  toda a negociação Forex.
- Cada broker pode mudar sufixos, universo, horário de sessão, histórico
  disponível e licenciamento. Não há cobertura 28/28 comprovada.
- Este importador é **separado** do contrato M15 com bid/ask de mercado da
  PR #1812; não o contorna e não alimenta `VALIDATED_DAILY` do Radar.
- Para estudos de OB/FVG, o próximo passo seria testar histórico suficiente,
  estrutura de preço, invalidadores, regras de risco e resultados fora da
  amostra. Ainda não há taxa de acerto validada.

## Decisão

**GO-LAB apenas para importação local e backtest sintético; HARD NO-GO para
publicação de preços, execução, AION, Worker e Render. R$ 0 de contratação.**
