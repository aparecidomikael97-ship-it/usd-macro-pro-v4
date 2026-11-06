# AtlasQuant Trader — EUR (HICP flash) + USD (CPI modelo), matriz 28 (LAB)

**Pesquisa e checkpoint: 06/11/2026.**

## Fontes oficiais já guardadas no laboratório

| Moeda | Medida e estágio econômico | Competência | Valor documental | Origem |
| --- | --- | --- | ---: | --- |
| EUR | Eurostat, inflação anual `HICP all-items` da zona do euro **EA21**, estimativa **flash** preliminar, não inflação final nem consenso | Outubro de 2026 | **4,0%** | https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04112026-ap (publicação 04/11) |
| USD | Fed de Cleveland, **nowcast de modelo** CPI headline YoY NSA, não CPI efetivo nem consenso | Outubro de 2026 | **3,74%** | https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting (página consultada 06/11) |

O documento Eurostat indica publicação completa de outubro **prevista para 18/11/2026**. O BLS prevê CPI de outubro para **10/11/2026 às 08h30 ET**. Os calendários podem mudar.

## Roteamento sem extrapolação

- **7 pares EUR** recebem contexto da publicação *flash* somente depois do portão documental conservador `05/11/2026 00:00 UTC`.
- **7 pares USD** recebem contexto de previsão de modelo somente depois da pesquisa conservadora `07/11/2026 00:00 UTC`.
- Há **1 interseção**: `EUR/USD`, que mostra os dois lados para outubro, mas assinala expressamente **estágios e metodologias diferentes**.
- Ao todo, **13** dos 28 pares têm pelo menos um desses dois contextos; **15** não recebem nenhum deles. A distribuição não representa cobertura macroeconômica completa.
- **Não calcular `4,0 - 3,74` como diferencial macro negociável.** A zona do euro usa HICP de estimativa flash (EA21); os EUA, CPI-U de previsão de modelo. A magnitude não mede força do euro contra o dólar, e nenhuma fonte é consenso de analistas para o mesmo evento.
- Antes das publicações completas, não inventar CPI efetivo, número de surpresa, acurácia ou viés direcional. Mesmo depois dos horários agendados, os dados **não** se tornam resultados até captura oficial autenticada.

O módulo `atlasquant_trader_g8_eur_hicp_usd_cpi_stage_context_lab.py` reaproveita os casebooks SHA-pinned de #1836, a auditoria documental EUR/USD existente e o roteamento dos 28 pares de #1837. Não cria recibo extra duplicado nem modifica o aplicativo.

**Resultados:** todos os 28 pares `D1=AGUARDAR`, `W1=AGUARDAR`; `ranked_currencies=[]`; `best_pair_of_day=None`; nenhum sinal, trade, worker, cron, HTTP ou custo adicional. Aguardam-se dados de outras moedas, surpresas de calendário verificadas e teste prospectivo de preço antes de qualquer saída operacional.
