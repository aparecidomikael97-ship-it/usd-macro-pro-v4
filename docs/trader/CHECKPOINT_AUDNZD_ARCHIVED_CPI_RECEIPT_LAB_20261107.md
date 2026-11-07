# AtlasQuant Trader — AUD/NZD: prova de conteúdo em documentos CPI arquivados (LAB)

**Data da revisão:** 07/11/2026. **Escopo:** prova de bytes e extração de valores macroeconômicos, não previsão do câmbio. **Status:** isolamento, sem merge/deploy/Worker/ordem, prioridade W1/D1 mantida.

## Resultado reproduzível

`atlasquant_audnzd_cpi_archive_receipt_lab.py` aceita os bytes de dois documentos da Biblioteca já guardados e verifica **hash SHA-256 exatamente igual ao snapshot usado nesta rodada**. Extrai:
- **AUD:** Tabela 17 XLSX oficial do ABS, `Data1`, série nacional `A2325846C`, cadência `Quarter`. Setembro/2025 na célula `J319` = **99.73** e setembro/2026 em `J323` = **103.64**. Fórmula `((103.64 / 99.73) - 1) * 100` = **3,920585...%**, reportada como **3,9% por arredondamento dos índices publicados**; não é número anual diretamente atestado na planilha.
- **NZD:** PDF resumo do CPI trimestral setembro/2026, página 1: `CPI all groups`, **3,7% a/a**; página 2: **0,7% t/t**. São números reportados pelo próprio documento arquivado, não calculados pelo modelo.
- Ambos os documentos referem o trimestre setembro/2026, mas **a equivalência metodológica/territorial e a consequência cambial NÃO estão comprovadas**.

## Proveniência: limites explícitos

| Fonte | Arquivo da Biblioteca | SHA256 dos bytes da cópia desta rodada |
| --- | --- | --- |
| ABS Tabela 17 | `/Pro/AUD_ABS_CPI_2026Q3_Table17.xlsx` | `59c89bf477cec8075dfa80f1c29f97654f16f148b11427bed35fbad869eb7d47` |
| Stats NZ PDF | `/Pro/NZD_CPI_2026Q3_StatsNZ_summary.pdf` | `c0c685d36bdaa6afcaabba7bd1b656e4b46120032eb41d0a4e6dc01af0901bb7` |

**Atenção:** estes hashes são das **cópias atualmente recuperadas da Biblioteca**, não certificações de bytes originais do servidor emissor; podem ser distintos de checksums registrados em pesquisas anteriores por migração/versão. O documento de origem da planilha XLSX está disponível em [ABS CPI setembro 2026](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release) (Tabela 17). O documento PDF Stats NZ está associado à página [CPI setembro 2026](https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/). Não foi atestada cadeia de custódia, versão histórica, assinatura do emissor, nem disponibilidade comprovável dos bytes antes de cada decisão passada.

A data mínima de pesquisa `2026-10-29T00:00:00Z` evita analisar um período *obviamente* anterior à publicação, mas **não substitui um relógio independente de publicação e captura**.

## Portões que seguem fechados

- Resultado **`LAB_TWO_DOCUMENT_VALUES_MATCH_ARCHIVED_BYTES_UNATTESTED`** significa apenas "esses dois arquivos conhecidos contêm esses valores".
- `historical_point_in_time_verified=False`, `issuer_origin_independently_authenticated=False`, `can_feed_live_radar=False`, `operational_bias=AGUARDAR`, `score_0_to_10=None`, `trade_authorized=False` sempre.
- A política seletiva 0–10 e o Motor de Regimes/posição institucional **não recebem esse recibo como sinal**.
- O módulo V2 de identidade da série (`atlasquant_cpi_series_contract_lab.py`) da PR #1848 continua separado. Integração direta só após validar horários/vintages/consenso e regra efetiva de dados trimestrais para ambas as moedas.
- Macro bilateral ainda precisa acrescentar juros aplicáveis, expectativa de trajetória, consenso/surpresa, micro/geopolítica e preço P-I-T antes de propor viés D1/W1 ou reação à notícia.

## Verificação da rodada

- Python 3.13, `python -m unittest -v test_atlasquant_audnzd_cpi_archive_receipt_lab.py`: **12/12 PASS**, com os 2 documentos da Biblioteca materializados localmente.
- `python -m py_compile` dos dois arquivos: OK.
- Hash Git blob dos arquivos na branch coincide com o conteúdo exato testado localmente (incluindo quebra de linha final).
- Na CI sem cópias dos documentos arquivados, **quatro testes marcados com `skipUnless` serão ignorados**, portanto uma suíte remota sem arquivos não substitui a rodada local. Nenhuma API paga, fonte de preços ou ordem foi usada.

**Próxima prioridade:** criar ponte de dados V2 + recibo por competência/fonte, depois expandir o mesmo padrão às 8 moedas e 28 pares. Preservar o Checkpoint Mestre, os filtros 0–10, micro e geopolítica sem deslocar o objetivo principal.
