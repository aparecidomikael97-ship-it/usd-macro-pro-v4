# AtlasQuant Trader — validador offline M15 → H1/H4 (LAB)

Data: 02/11/2026 · PR #1803 DRAFT · HARD NO-GO.

## Objetivo e fronteira

Preparar o recebimento futuro de dados Forex de um terminal pessoal sem
acessar, contratar ou redistribuir dados de corretora nesta etapa.

O módulo `atlasquant_trader_m15_broker_export_lab.py` recebe somente
objeto em memória contendo 28 pares G8 canônicos × 16 candles M15
**fechados** numa janela contínua de quatro horas (448 candles).
Requer dados completos dos 28 pares, identificação da fonte, link
HTTPS sem credenciais, exportação posterior ao encerramento da janela,
timezones UTC declarados, OHLC decimal válido e ausência de lacunas,
duplicação e desalinhamento entre os pares.

A partir de cada conjunto de M15:
- H1: agrega quatro candles M15, produzindo quatro candles H1 por par;
- H4: agrega dezesseis M15, produzindo um candle H4 por par;
- open = primeira abertura; close = último fechamento; high/low =
  máximos/mínimos do grupo; período e origem preservados.

**Concessão técnica deliberada:** a janela H4 começa em 00/04/08/12/16/20
UTC. A H4 de uma corretora com início de sessão ou fuso próprio pode
ser diferente. O código não a representa como H4 nativa da corretora.
O rótulo `AGGREGATED_UNVERIFIED_M15_UTC_NOT_BROKER_NATIVE` permanece visível.

Apenas `UTC_DECLARED_UNATTESTED`, `BID_OHLC_UNVERIFIED`
e `UNREVIEWED_PERSONAL_LAB_ONLY` são aceitos; não há preço ASK,
spread executável, prova de relógio de broker, licença comercial nem
custódia de ponto-no-tempo. Um resultado estruturalmente completo
continua **não validado como preço real**, sem garantia de que os
28 pares sejam 28 fontes independentes.

## Testes

`test_atlasquant_trader_m15_broker_export_lab.py` tem 16 cenários
**exclusivamente sintéticos**, cobrindo 28 pares, 448 barras, OHLC
agregado, faltas de ativo/candle, repetição/desordem, UTC desalinhado,
barra ainda em formação, preço inválido, campos de permissão indevidos
e recusa de autorização operacional. Integrado ao Quality CI.

Saídas invariáveis: `real_bias_28_pairs=null`,
`can_feed_live_radar=false`, `can_feed_real_oos=false`,
`backtest_oos_authorized=false`, `trade_authorized=false`,
`worker_enabled=false`, `scheduler_enabled=false`.

## Próximo portão

Identificar a corretora/terminal do proprietário e obter, se ele
autorizar, pequena exportação local **pessoal** de dados; primeiro
verificar licença, horários reais, símbolos, BID/ASK e divergências
entre H4 UTC e H4 nativa. Não guardar arquivo proprietário em
repositório público sem licença expressa. Verificação futura de OOS
deve separar informação disponível antes da previsão e resultado
posterior; sem antecipar taxa de acerto.

**Nenhuma API/conta/assinatura foi acionada; nenhum merge, deploy,
cron, Worker AION, ordem ou modificação visual foi feito.**
