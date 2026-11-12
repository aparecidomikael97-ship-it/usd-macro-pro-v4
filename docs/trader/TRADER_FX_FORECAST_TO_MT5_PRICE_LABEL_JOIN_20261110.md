# AtlasQuant Trader — ligação entre viés prévio alegado e vela MT5 futura (LAB)

**Data:** 10/11/2026. **Estado:** laboratório, sem publicação, sem ordens.

## Descoberta metodológica importante

O relatório anterior do MT5 calculava o **fechamento de uma vela para o
fechamento da seguinte**. Se o viés é registrado *antes* de a segunda vela
começar, o fechamento da primeira vela pode ainda não estar disponível no
instante exato da previsão. Usá-lo como preço de entrada conhecido seria risco
de *look-ahead* (informação do futuro). Além disso, um gap entre velas pode
inverter a direção do fechamento-a-fechamento em relação à vela em si.

A porta `atlasquant_trader_mt5_forward_label_gate_lab.py` preserva sua variação
histórica anterior para diagnóstico e **agora também** retorna:

- `exit_bar_open_price_documentary`: abertura da segunda vela;
- `exit_bar_open_to_close_bps_documentary`: movimento de **abertura até fechamento
  da segunda vela**;
- `observed_exit_bar_body_direction_only`: alta, baixa ou estabilidade do corpo
  dessa vela, não previsão nem resultado de negócio.

Um teste com gap sintético mostra fechamento-a-fechamento **DOWN**, enquanto a
segunda vela tem corpo **UP**. O motor não equipara as duas definições.

## Nova porta de junção

`atlasquant_trader_fx_forecast_price_join_lab.py` implementa
`join_fx_forecast_to_next_mt5_bar_lab(...)` com estas condições cumulativas:

1. Revalidar a cadeia de previsões e os recibos/hash final **alegados** com a
   porta `verify_fx_precommit_receipts_lab` (sem considerar o horário atestado).
2. Selecionar exatamente um `opportunity_id`, com horizonte `D1` ou `W1`.
   `M1` é bloqueado: o arquivo MT5 AM12 contém M15/D1/W1, não M1.
3. Comparar a janela da previsão, também alegada, com a abertura e fechamento
   **nominal** da segunda vela: emissão anterior à abertura; fim igual a
   abertura + duração padrão; resultado posterior à conclusão da janela.
4. Reexecutar o verificador **sobre os bytes gzip originais fornecidos pelo
   chamador e seu manifesto**; par, timeframe, SHA, OHLC, monotonicidade e
   ausência de gap na seleção devem passar. Não aceitar simplesmente um JSON
   de resultado sem reler a fonte.
5. Se tudo passa, mostrar apenas a junção documental e a variação do **corpo
   da segunda vela**. Não calcula nem incrementa acertos e não compara essa
   variação com entrada/saída executável, spread, slippage ou lucro.

É uma análise estrutural, não um motor de backtest. Mesmo com corpo de vela
observado e hash local consistente, a data efetiva de emissão do viés, a
autenticidade dos macroeconômicos e a interpretação do epoch UTC/sessão MT5
**ainda não são atestadas por fonte independente**.

## Estados e bloqueios permanentes

- Junção documental possível: `LAB_FORECAST_AND_FUTURE_BAR_DOCUMENTARY_JOIN_UNATTESTED`.
- Dados ausentes/incompatíveis: `LAB_FORECAST_PRICE_JOIN_BLOCKED`.
- `is_hit=null`, `real_accuracy_count_increment=0`,
  `validated_accuracy=null`, `calibrated_probability=null`.
- `external_receipt_timestamp_authenticated=false`,
  `macro_vintages_independently_authenticated=false`,
  `mt5_broker_candle_utc_authenticated=false`,
  `historical_point_in_time_verified=false`.
- `can_feed_validated_backtest=false`, `operational_bias=AGUARDAR`,
  `publishable=false`, `trade_authorized=false`.

Mesmo uma junção **sintética** aparentemente bem-sucedida não prova que o
AtlasQuant acertou um viés em tempo real. O sistema ainda precisa de recibo
externo confiável, fonte macro bilateral verificável e calendário/sessão da
corretora antes de autorizar avaliação de assertividade. Lacuna GBP/NZD D1 de
30/09/2025 segue bloqueada quando a janela a atravessa; não se preenchem velas.

## Execução de testes

- 14 testes novos de junção documental, incluindo D1/W1, abstenção, M1
  bloqueado, forecast adulterado após recibo, hash final falso, evento não
  resolvido, arquivo gzip violado, timestamp de candle inexistente e gap.
- 1 teste adicional no módulo de preço demonstra divergência entre corpo de
  vela e fechamento-a-fechamento devido a gap sintético.
- Suíte local `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **269 testes aprovados** nesta rodada.
- **Nenhum arquivo MT5 real** foi reaberto aqui; somente séries e previsões
  sintéticas. Nenhum registro real foi emitido. Nenhum Worker, deploy, merge,
  alteração na Pepperstone ou no aplicativo publicado.

## Passo seguinte

Definir e testar a cadeia de custódia de um recibo de previsão **com instante
de aceitação gerado por serviço externo confiável**, além de captura e
autenticação point-in-time do documento de cada moeda. Uma cadeia de SHA-256
gerada localmente não consegue provar sozinha a anterioridade de uma previsão.
