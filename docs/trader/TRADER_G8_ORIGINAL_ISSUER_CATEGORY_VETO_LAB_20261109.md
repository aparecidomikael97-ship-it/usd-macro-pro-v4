# AtlasQuant Trader — fonte original compatível com CPI e juros (LAB)

**09/11/2026 (Cuiabá); PR #1851 em rascunho.** Nenhuma ordem, mudança de conta, merge, publicação ou custo adicional.

## Lacuna identificada

O `atlasquant_trader_g8_macro_asof_lab.py` antes aceitava `source_type` entre `CENTRAL_BANK` e `OFFICIAL_STATISTICS_OFFICE` sem relacioná-lo ao indicador. Um recibo sintético de **CPI publicado como se fosse uma decisão de banco central** ou uma **taxa de política monetária publicada como se a autoridade decisora fosse um instituto de estatística** poderia passar pela checagem estrutural, afetando o contexto documental de pares.

## Trava implementada

O tipo informado deve corresponder à **categoria do emissor original**:

| Indicador | Categoria exigida |
| --- | --- |
| `CPI_YOY` | `OFFICIAL_STATISTICS_OFFICE` |
| `POLICY_RATE` | `CENTRAL_BANK` |

O receptor com categoria incompatível agora retorna `LAB_BLOCKED / INDICATOR_ORIGINAL_ISSUER_CATEGORY_MISMATCH`. A matriz bilateral conserva a rejeição nos sete pares que contêm a moeda afetada, sem contaminar os outros 21 pares.

**Exemplos institucionais:** o CPI dos EUA é publicado pelo BLS (<https://www.bls.gov/cpi/home.htm>), enquanto as decisões da taxa federal são do Federal Reserve/FOMC (<https://www.federalreserve.gov/monetarypolicy/openmarket.htm>). Na área do euro, Eurostat divulga HICP (<https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-01092026-ap>) e o BCE publica suas decisões de juros (<https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html>).

## Limites e testes

- **48/48 testes locais PASS** com `python -m unittest -v test_atlasquant_trader_g8_macro_asof_lab test_atlasquant_trader_g8_macro_matrix_pit_lab` (inclui as duas novas regressões).
- 28 pares testados contra as duas categorias trocadas; matriz de oito moedas também testa, para cada moeda, rejeição exatamente dos sete pares afetados.
- Esta é apenas uma **checagem de categoria declarada pelo chamador**. Um documento falsificado ou hospedado em site de terceiro ainda pode alegar categoria correta. Nome, endereço oficial, bytes originais, hash, instante de publicação e método de coleta precisam ser corroborados separadamente.
- Não há fonte real nova capturada nesta etapa, análise point-in-time autenticada, probabilidade calibrada ou acerto direcional mensurado.
- Permanecem `source_origin_authenticated=False`, `historical_point_in_time_verified=False`, `operational_bias=AGUARDAR`, `trade_authorized=False`, `publishable=False`.

**Próxima etapa:** vincular recibos por país ao emissor efetivo (BLS, Eurostat, ONS, MIC/Statistics Bureau, FSO, Statistics Canada, ABS, Stats NZ e respectivos bancos centrais), preservar revisões/vintages e testar uma coorte prospectiva com horários confiáveis. O relógio AM12 permanece pendente; esta regra não altera nem normaliza timestamps do MT5.
