# AtlasQuant Trader — PPI 13/11/2026: contexto de spread M15 (LAB)

## Lacuna tratada

O estudo `atlasquant_trader_ppi_one_event_study_join_lab.py` mede movimentos do USD em 7 pares Forex, mas anteriormente não apresentava sequer o campo `spread` dos 17 candles M15 arquivados pelo MT5. Seria imprudente interpretar qualquer movimento como retorno executável sem conhecer custos de negociação.

A nova auditoria `atlasquant_trader_ppi_m15_spread_context_lab.py` exige que o arquivo completo de sete pares passe novamente pelo guardião original de OHLC, cronologia UTC, hashes e janela fechada. Depois relê cada CSV e revalida seu SHA-256, evitando usar silenciosamente spreads alterados após a auditoria de preços. Não toca no MT5 nem na conta.

Para cada par, entrega **somente valores em pontos do próprio símbolo**:
- amostra do campo `spread` no candle anterior ao anúncio (13h15–13h30 UTC);
- amostra do campo `spread` no primeiro candle depois da divulgação (13h30–13h45 UTC);
- **maior dos 16 valores de `spread` por barra M15** após divulgação (até 17h30 UTC), não maior spread intrabar;
- mediana dos 16 valores de `spread` por barra;
- razão entre a maior amostra e a amostra anterior apenas **dentro do mesmo par**, quando a amostra anterior for positiva;
- quantidade de amostras zero (zero pode indicar ausência de cotação ou outra particularidade do fornecedor; nunca comprova custo zero).

Esses campos são amostras descritivas das barras e **não necessariamente máximo, média nem fechamento do spread dentro de cada candle**; o método de agregação do servidor MT5 não foi atestado. Os pontos de EURUSD, USDJPY etc. **não são diretamente comparáveis** sem verificar o tamanho de ponto, dígitos e convenções do broker. A leitura da barra M15 também **não comprova** bid/ask capturável no momento, liquidez, slippage, comissão ou retorno líquido. Não há limiar arbitrário para declarar uma oportunidade boa ou ruim; o mercado futuro determinará se é possível calibrar algum.

O relatório conjunto de PPI agora exige esse estágio documental além dos componentes congelados. A origem real das 119 velas e o servidor Pepperstone continuam **não atestados**; o terminal usado em auditoria anterior mostrou MetaQuotes-Demo no navegador e não se pode assumir proveniência.

## Portas e cronologia

- Até 13/11/2026 13h30 UTC: nenhum dado oficial PPI de outubro pode ser usado como já publicado.
- Até 13/11/2026 17h30 UTC: não se pode reivindicar os 17 candles fechados da janela de 4 horas.
- Depois disso: a pessoa pode optar por captura manual no AM12; ainda não há comprovação externa de hora do broker nem de custo executável.
- O conjunto de sete pares representa **um evento econômico**, nunca sete provas independentes.

Todos os relatórios permanecem `operational_bias=AGUARDAR`, `publishable=false`, `trade_authorized=false`, `validated_accuracy=null` e `calibrated_probability=null`.

## Verificação

Novo teste `test_atlasquant_trader_ppi_m15_spread_context_lab.py` cobre sete pares, spread relativo por símbolo, maior valor entre amostras (não pico intrabar), zeros isolados e totais, janela fechada, corrupção, símbolo faltante, recebimento prematuro, spread inválido e symlink. O teste integrado `test_atlasquant_trader_ppi_one_event_study_join_lab.py` exige o novo estágio e impede classificação de retorno executável.

Todos os testes são sintéticos e não constituem backtest, demonstração causal, acerto preditivo ou recomendação de investimento. Sem automação, merge, publicação, custo ou ordem.

### Revisão da semântica do spread — 11/11/2026

A revisão substitui nomes como `post_release_four_hour_peak_spread_points`, que poderiam sugerir o **pico intrabar real**, por `max_of_16_post_release_m15_bar_spread_samples_points`. O relatório consolidado passa a usar `m15_bar_spread_samples_not_intrabar_peak_or_transaction_cost` e inclui `intrabar_max_spread_not_measured=true`. O módulo mantém `intrabar_peak_spread_verified=false`, `timestamped_bid_ask_quotes_verified=false` e `bar_spread_aggregation_method_verified=false` inclusive quando todos os dados sintéticos passam.

Não se altera a metodologia congelada de preços, nem o calendário do PPI, nem a janela dos 7 pares. São ajustes de interpretação e travas de afirmações de custo. Não converter essas amostras em spreads executáveis ou retornos líquidos.
