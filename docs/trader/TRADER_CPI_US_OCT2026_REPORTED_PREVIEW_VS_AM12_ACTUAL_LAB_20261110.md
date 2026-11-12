# AtlasQuant Trader — CPI EUA out/2026: realizado × expectativa documentada — 10/11/2026

**LAB / PESQUISA RETROSPECTIVA / NÃO É BACKTEST POINT-IN-TIME / NÃO LIBERAR SINAL.**

## Contexto e fontes (documentos distintos)

**Realizado:** [BLS, Consumer Price Index, October 2026](https://www.bls.gov/news.release/archives/cpi_11102026.htm), comunicado USDL-26-1685, divulgado 10/11/2026 08h30 Nova York. A cópia HTML do usuário no AM12, salva **após o evento**, foi examinada e preservada **somente no PC**:
- `Documentos/AtlasQuant/Trader/BLS_CPI_20261110/BLS_CPI_OCT2026_BROWSER_SAVED_20261111T001111Z.html`
- SHA-256: `7041541ddfc6fc155e33eab0d191e6dff6ba44c1b847921f1926cf9425126c18`
- Metadado local de criação: `2026-11-11T00:11:11.243655Z`. **Não prova hora real de primeira publicação**. URL na Zone.Identifier é indício de origem, não assinatura do BLS.
- O módulo de extração `atlasquant_trader_us_oct2026_cpi_release_text_guard_lab.py` (atualizado) identificou **CPI-U all items +0.4% SA MoM**, **core all-items less food and energy +0.3% SA MoM**. A comparação headline anual continua indisponível porque não existe o índice de out/2025.

**Expectativa de mercado descrita antes da divulgação:** [FXStreet — US CPI preview, 09/11/2026 22:31:21 GMT](https://www.fxstreet.com/analysis/us-cpi-preview-moderation-on-the-horizon-but-underlying-pressures-linger-202611092231), artigo que informa o consenso divulgado para **headline +0.3% SA MoM** e **core +0.2% SA MoM**. **A primeira versão nem a hora da primeira publicação foram atestadas independentemente; a página foi localizada retrospectivamente.** É um dado de *pesquisa documental*, não prova de pré-captura pelos nossos workers.
- [Reuters, cobertura de 10/11/2026 após a divulgação](https://www.reuters.com/business/view-hot-october-inflation-report-rattles-markets-2026-11-10/) confirmou o headline 0.4 realizado versus 0.3 projetado e descreveu as reações do mercado, mas notícia pós-evento **não é** fonte de consenso original pré-evento.

## Comparação documental, não sinal

| Métrica | Consenso reportado antes do evento | Realizado BLS documentado | Diferença aritmética |
|---|---:|---:|---:|
| CPI-U headline **SA MoM** | +0.3% | +0.4% | **+0.1 ponto percentual** |
| CPI-U core **SA MoM** | +0.2% | +0.3% | **+0.1 ponto percentual** |
| CPI anual de out/2026 | não comparável | não divulgado | **NÃO CALCULAR** |

**Interpretação apenas conceitual:** maior inflação relativa a uma previsão pode resultar em expectativa de juros mais altos, maior rendimento nominal e suporte ao USD, mas **não prova tendência de um par** e pode já estar precificada. Não autorizar compra USDJPY/venda EURUSD, ouro ou índices por esse cálculo isolado.

## Entrega de engenharia

Novos arquivos na PR draft:
- `atlasquant_trader_us_oct2026_cpi_documentary_comparison_lab.py`
- `test_atlasquant_trader_us_oct2026_cpi_documentary_comparison_lab.py`

O código recebe o **HTML local bruto**, verificando o SHA do recibo e interpretando conteúdo pela implementação já auditada, além da alegação documental da fonte de expectativa (data e métrica SA MoM exatas). Calcula apenas `headline_retrospective_difference_pp_claim` e `core_retrospective_difference_pp_claim`, e impede:
- comparar ano contra mês, raw level contra percentagem, ou sazonalizado contra não sazonalizado;
- inserir documento BLS com hash incompatível, fonte enganosa, publicação/captura no futuro ou antes do embargo;
- usar outra data/fonte/valor de expectativa silenciosamente;
- afirmar que a pesquisa de Reuters foi capturada antes do evento ou que timestamp local representa atestado de emissor;
- retroagir o resultado desta pesquisa a 10/11 13h30 UTC como se o sistema o conhecesse.

**Resultados de testes AM12/Python 3.12:** dez testes sintéticos desta nova etapa, todos PASS; execução manual adicional contra o arquivo de HTML completo do navegador, também PASS:
`headline=0.4`, `core=0.3`, `forecast_headline=0.3`, `forecast_core=0.2`, diferenças `0.1` e `0.1`.
Recibo local integral: `Documentos/AtlasQuant/Trader/BLS_CPI_20261110/BLS_CPI_OCT2026_RETROSPECTIVE_COMPARISON_RECEIPT_LAB.json`.

O workflow `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` executa o módulo e os testes em Python 3.11 e 3.12, **sem acessar fontes externas**. Os testes de CI são sintéticos e não contêm o HTML original.

**Status explícito:** `statistically_verified_surprise=null`, `directional_usd_signal=null`, `eurusd_directional_bias=null`, `validated_accuracy=null`, `operational_bias=AGUARDAR`, `backtest_eligible=false`, `publishable=false`, `trade_authorized=false`, custo novo zero.

## Próximos critérios de avanço

1. Para os **próximos eventos** macro, guardar as expectativas **antes** da divulgação com captura original (origem, timestamp UTC, arquivo e hash) e, depois, o realizado oficial.
2. Separar informação de evento, resposta de preços e previsão direcional: medir efeito incremental sobre os pares USD (sem leakage) e depois G8.
3. Não vender percentuais de assertividade nem liberar alertas operacionais antes de resultados fora da amostra com custos e sinal de abstenção; PR ainda draft.
4. O AtlasQuant Flow v1.1 continua arquivado e fora de escopo.
