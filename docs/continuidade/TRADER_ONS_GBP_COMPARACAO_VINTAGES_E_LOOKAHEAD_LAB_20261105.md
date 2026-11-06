# AtlasQuant Trader — comparação de versões da inflação GBP e proteção histórica (LAB)

**Data:** 05/11/2026. **Escopo:** somente comparação offline de dois JSONs fornecidos; nenhuma coleta, negociação ou publicação.

## Problema evitado

O histórico econômico pode ser revisado. Usar hoje a taxa que aparece num banco de dados para simular uma decisão feita semanas atrás cria **viés de antecipação (*lookahead*)**. A página oficial de versões anteriores do ONS (https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous) mostra datas de versões substituídas, mas **data de substituição não comprova a hora exata de publicação da versão substituta**. Uma data isolada não autoriza um backtest intradiário.

## Contrato entregue

O módulo `atlasquant_trader_ons_gbp_vintage_comparison_lab.py` recebe dois blobs JSON e dois instantes UTC fornecidos pelo pesquisador: coleta local e instante histórico da hipótese. Reaproveita a validação rígida da série ONS `D7G7`, dataset `MM23` e campo `months`.

- Exige datas de divulgação **declaradas** crescentes e preserva SHA-256 de cada blob.
- Compara exclusivamente os últimos 15 meses observados em cada versão, mês a mês; detecta taxas revisadas, taxa faltante que virou número (ou o contrário), observações novas e meses fora da janela. Nunca interpreta um mês ausente como zero.
- Valores numericamente idênticos, como `3.1` e `3.10`, não são revisão.
- Se a data declarada da versão for **posterior** ao corte histórico, classifica-a como bloqueada. Se for o **mesmo dia**, o horário da publicação é desconhecido: também bloqueia. Até datas anteriores ao corte permanecem **não atestadas**, porque a origem e a disponibilidade histórica efetiva não foram provadas.
- A lista de meses removidos significa apenas **fora da janela comparada**; não afirma apagamento na base histórica.
- Resultado **sempre** `usable_in_historical_backtest=false`, `point_in_time_available_verified=false`, `fx_bias=null`, `operational_bias=AGUARDAR`, sem autorização para Radar, Worker, agendador ou trading.

## Exemplo estritamente sintético

Uma versão declarada em 16/09/2026 traz agosto `3.1`; outra, declarada em 21/10/2026, traz agosto `3.2` e acrescenta setembro `3.5`. O comparador identifica uma diferença para agosto. **Esses números são exclusivamente dados de teste**, não uma afirmação de que o ONS revisou agosto de verdade.

Um backtest hipotético datado de 20/10/2026 não pode usar a versão declarada em 21/10. Um backtest de 21/10 permanece bloqueado por falta de hora comprovada. Um backtest de 22/10 continua não autorizado para uso, pois o simples calendário não atesta disponibilidade efetiva.

## Pendências para homologação

1. Coletar e arquivar **bytes originais** das versões disponibilizadas pelo ONS, com URL, cabeçalhos de resposta, hora e hash de coleta, sem custos adicionais.
2. Comprovar independente e historicamente quando os valores eram conhecidos para cada instante de decisão, evitando confundir data de divulgação, data de captura atual e data de substituição de arquivo.
3. Validar formato real da API contra o leitor exploratório; verificar direitos de redistribuição.
4. Só depois validar preços Forex independentes, consensos pré-evento e impacto histórico; jamais inferir força de moedas de uma diferença de CPI entre metodologias.

**HARD NO-GO**: sem merge, deploy, Render, assinatura, Worker, trading ou alteração da interface da PR #1816. Etapa da Draft PR #1815.
