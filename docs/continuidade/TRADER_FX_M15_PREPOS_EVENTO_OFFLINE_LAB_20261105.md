# AtlasQuant Trader — prova estrutural de candles M15 em eventos (LAB)

## Por que este contrato existe

Para testar se uma leitura macro teria antecipado corretamente um movimento em **EUR/USD** (e posteriormente nos **28 pares G8**), precisaremos de preços com horários verificáveis **antes e depois** do instante de um evento. As taxas diárias de referência do BCE e as observações H.10 do Fed não demonstram o comportamento do preço no M15.

O MetaTrader 5 documenta a interface `copy_rates_range`, cujos registros têm: `time` (Unix UTC, abertura do candle), `open`, `high`, `low`, `close`, `tick_volume`, `spread` e `real_volume`. A documentação recomenda expressamente trabalhar em UTC: `https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py` e `https://www.mql5.com/en/docs/constants/structures/mqlrates`.

Esta etapa preparou apenas **um auditor de dados offline** chamado `atlasquant_trader_fx_m15_offline_price_window_lab.py`. Não conectou MetaTrader, corretora, conta ou histórico real, nem requisitou dados pagos. **Os testes são inteiramente sintéticos.**

## Contrato V1 — o que ele verifica

- Recebe exclusivamente **bytes JSON arquivados** no esquema próprio `ATLASQUANT_MT5_M15_OFFLINE_EXPORT_V1`, com os oito campos MT5, `timeframe=M15`, símbolo no conjunto de oito moedas G8, Unix **segundos UTC** e valores OHLC em **strings decimais** para reprodutibilidade. É um formato normalizado proposto para exportação futura, não um formato nativo prometido pelo MT5.
- Recebe `captured_at_utc`, `as_of_utc`, `event_at_utc` com timezone; rejeita datas futuras, candles ainda abertos na captura, tempo sem alinhamento de 15 minutos, duplicatas, desordenação, buracos, valores numéricos inválidos, OHLC impossível e volumes/spreads malformados.
- Exige **4 candles M15 já fechados antes** e **4 candles M15 completos iniciados após** o instante do evento. Se o evento ocorre **dentro** de um candle, esse candle não é contado nem como pré nem como pós-evento: precisa existir e é excluído. Sem preenchimento de candles faltantes.
- Só devolve SHA-256 do arquivo, bytes, horários e **contagem das janelas**. Não calcula retorno, acerto, MFE/MAE, slippage, spread executável, entrada ou direção operacional.

## O que ainda NÃO está comprovado

Um JSON pode conter candles sintéticos, alterados ou revisados. Por isso, até mesmo a janela `LAB_M15_EVENT_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED` mantém:

`broker_identity_independently_verified=false`, `timestamp_origin_independently_verified=false`, `price_side_broker_attested=false`, `independent_execution_prices_verified=false`, `historical_point_in_time_eligible=false`, `historical_backtest_accuracy_verified=false`, `m15_trade_ready=false`, `fx_bias=null`, `operational_bias=AGUARDAR`, `trade_authorized=false`, `worker_enabled=false`, `scheduler_enabled=false`, `new_cost_brl=0`.

São necessárias **proveniência real do fornecedor, distinção bid/ask, precisão/escala do spread, revisão histórica, disponibilidade do consenso antes do evento, permissões de uso de mercado e timestamps comprováveis** para passar de estrutura para teste real de assertividade. Mesmo com uma exportação legítima, não podemos transformar preços retrospectivos em testemunho de disponibilidade histórica sem provas extras.

**Entrega:** testes de contratos sem custo e sem integração, em branch LAB da PR #1815 Draft. A PR #1816 da interface fica intacta. Sem merge, deploy, Worker, Render, operações ou novas assinaturas.
