# AtlasQuant Trader — HistData M1 Bid, EST fixo e janela de eventos (LAB)

**Data:** 2026-11-05. **Estado:** preparação exclusivamente offline; fonte candidata, não homologada nem conectada ao Radar.

## Objetivo e origem

Investigar uma via sem assinatura paga para estudar, no futuro, o movimento intradiário de EUR/USD antes e depois de anúncios macroeconômicos. O HistData informa que seus arquivos **Generic ASCII M1** são `YYYYMMDD HHMMSS;OpenBid;HighBid;LowBid;CloseBid;Volume`, com o horário **EST fixo, UTC−05:00, sem ajuste de verão**. Os M1 são **Bid**, não incluem Ask ou spread verificável e o volume de M1 aparece como zero segundo a especificação.

- Especificação publicada pela fonte: https://www.histdata.com/f-a-q/data-files-detailed-specification/
- FAQ e aviso de horário fixo: https://www.histdata.com/f-a-q/
- Página de download manual gratuito, ainda não acionada neste exercício: https://www.histdata.com/download-free-forex-data/

**Cuidado fundamental:** EST fixo **não equivale** ao fuso `America/New_York` nos meses de verão. O leitor usa deslocamento UTC−5 o ano todo. Por exemplo, `2026-07-28 12:00 EST fixo` corresponde a `2026-07-28 17:00 UTC`, e não 16:00 UTC.

## Contrato preparado

Arquivo: `atlasquant_trader_histdata_m1_bid_window_lab.py`; testes `test_atlasquant_trader_histdata_m1_bid_window_lab.py`.

- Entrada: **bytes locais** do CSV `DAT_ASCII_EURUSD_M1_YYYYMM.csv` (G8 suportado no contrato), nome, símbolo, horário UTC da captura, UTC de conhecimento e UTC do evento. **Não há downloader**, autenticação, conta MT5 ou acesso à corretora.
- Rejeita mistura de meses, moeda errada, linha malformada, caracteres não ASCII, números anômalos, OHLC impossível, linha duplicada/invertida, volume não nulo, minuto posterior à captura e ausência de qualquer minuto requerido.
- Requer **4 candles M15 completos anteriores** e **4 posteriores** ao evento; cada candle agrega exatamente quinze observações M1 ordenadas. Se evento cai dentro de candle M15, o candle atravessado é verificado mas excluído de pré/pós. Nunca preenche lacunas nem cria preços.
- Resposta restrita a integridade estrutural, hash SHA-256, horários e contagens; **não divulga preço, retorno, direção, taxa de acerto nem estatística de trade**.
- As flags `ask_prices_present`, `spread_at_event_known`, `downloaded_source_authenticity_verified`, `market_data_product_license_verified`, `historical_point_in_time_eligible`, `m15_execution_price_verified`, `historical_backtest_accuracy_verified`, `trade_authorized`, `can_feed_live_radar`, `worker_enabled`, `scheduler_enabled` e `publishable` permanecem `false`. `fx_bias=null` e `operational_bias=AGUARDAR` mesmo após validação estrutural.

## Evidência e limitações

Executados **18 testes novos sintéticos** do leitor. Na regressão local com os contratos econômicos anteriores, **267 testes aprovados**. A cobertura inclui ausência de um minuto, candlestick atravessando evento, horário de verão, OHLC incorreto, timestamp malformado, caracteres inválidos e não promoção indevida para sinal.

**Não foi baixado nem arquivado qualquer CSV real HistData neste avanço**. A disponibilidade de arquivos de 2026, identidade da cópia de dados, precisão da fonte, licença para redistribuir/reutilizar comercialmente e condições do site não foram comprovadas. A indicação de download gratuito não é autorização automática de uso em produto para clientes. Não se deve incluir arquivo de terceiros no repositório ou distribuí-lo antes de checar licença e direitos.

Mesmo uma captura válida obtida hoje é retrospectiva: não prova automaticamente qual versão de consenso/preço estava disponível a um operador **antes** do evento. Para avaliar assertividade serão necessárias provas independentes da origem e cronologia das notícias, do consenso pré-anúncio, da disponibilidade de preços Bid/Ask e custos de execução; seguida de validação fora da amostra. Os candles de referência BCE e H.10 Fed seguem **não equivalentes a cotações M15 executáveis**.

## Estado operacional

Branch da **Draft PR #1815**, preservando a PR #1816 da interface. **LAB / HARD NO-GO**: sem merge, deploy, Render, Worker, agendamentos, compra de dados, API paga, integração ao Radar ou operação real. Custo novo **R$ 0**.
