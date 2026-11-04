# AtlasQuant Trader — replay M15 de execução hipotética (LAB)

Data: 04/11/2026. Escopo: avaliação de cenários **pré-anotados** para
pesquisa de OB, FVG e pullback. Nenhum setup é gerado automaticamente nesta
etapa; nenhum número de acerto ou rentabilidade real é afirmado.

## Módulo

`atlasquant_m15_execution_replay_lab.py`,
`replay_m15_setup(payload, now=...)`, puro e offline.

Entrada:
- `schema=ATLASQUANT_M15_EXECUTION_REPLAY_LAB_V1`;
  `state=OFFLINE_RESEARCH`; `timeframe=M15`
- Par canônico G8 e lado `BUY` ou `SELL`
- Nome do setup apenas descritivo: `FVG`, `ORDER_BLOCK` ou `PULLBACK`
- OHLC positivos de candles M15 fechados, UTC, sequenciais sem lacunas
- `signal_bar_index` apontando para uma vela anterior à entrada
- `signal_confirmed_at` **igual ao fechamento** da vela do sinal;
  a entrada hipotética é no preço de abertura da vela imediatamente seguinte
- `stop_mid` e `target_mid` fixados antes da entrada
- `point_size`, `spread_points_assumed`, `slippage_points_assumed`
  positivos/não negativos, **exigidos como hipóteses** e não como custos reais

Para compra, a entrada simulada piora pela metade do spread mais slippage;
a saída também piora por esses custos. Para venda, os sinais são invertidos.
O risco unitário é a diferença adversa entre entrada e stop executados
sob as hipóteses fornecidas. O resultado é `R = PnL / risco`.

## Regras conservadoras

1. Horário do sinal após a entrada, candles futuros, lacunas, datas sem fuso,
   preços OHLC inconsistentes, alvo/stop do lado errado e custos inválidos
   => `BLOCKED`.
2. Em uma vela que toca stop **e** alvo, assume-se **stop primeiro**.
   Não se tenta adivinhar a sequência intrabar com OHLC.
3. Se o horizonte acabar sem tocar stop ou alvo, retorna
   `UNRESOLVED_NO_EXIT` e `net_r=null`. Não é vitória, derrota nem
   resultado realizado; não pode entrar em win rate.
4. Não considera liquidez, slippage real, gap de execução, horário de notícia,
   spread variável, comissões, swap, tamanho de posição ou execução em exchange.
5. Um timestamp informado para o sinal não comprova que o setup foi detectado
   sem olhar o futuro. Essa garantia exige gerador de sinais testado com
   regras causais e caminhada temporal em dados reais.

Saída **sempre** `RESEARCH_ONLY` (ou `BLOCKED`), com:
`source_authenticated=false`, `signal_causal_verified=false`,
`spread_slippage_verified=false`, `profitability_verified=false`,
`publishable=false` e `trade_authorized=false`.

## Futuros passos

- Definir FVG/OB com formação, mitigação, invalidação e gatilho verificáveis;
  não decidir a lógica retrospectivamente por operação vencedora.
- Alinhar contexto W1/D1/H4, execução M15 e, se necessário, confirmação M5.
- Incluir amostras fora do período de ajuste, custos reais por par,
  recusas por notícias/spreads e estatísticas com intervalos de incerteza.
- Só depois considerar curvas de resultado, ranking de estratégias ou
  afirmações sobre assertividade.

Não altera Radar publicado, Render, AION, Worker ou operação. R$ 0 adicional.
