# AtlasQuant Trader — pisos conhecidos de publicação CPI para oito moedas (LAB)

Data da revisão: 2026-11-10. Esta tabela é pesquisa documental retrospectiva
de uma **amostra específica de divulgação**, não um arquivo original custodiado
no momento da primeira publicação. `as-of` sem prova externa permanece NO-GO.

## Rejeições de datas impossíveis na matriz G8

| Moeda / período | Primeiro limite admitido em UTC | Base do limite |
| --- | --- | --- |
| USD set/2026 | 14/10/2026 12:30Z | BLS: 08h30 EDT explícito |
| USD out/2026 | 10/11/2026 13:30Z | BLS: 08h30 EST explícito; YoY continua indisponível por falta de out/2025 |
| EUR set/2026 FINAL/sem estágio | 17/10/2026 00:00Z | Eurostat publicou em 16/10; próximo dia UTC conservador |
| GBP set/2026 | 21/10/2026 06:00Z | ONS: 07h00 BST explícito |
| CAD set/2026 | 20/10/2026 00:00Z | Statistics Canada publicou em 19/10; próximo dia UTC conservador |
| AUD set/2026 | 28/10/2026 00:30Z | ABS: 11h30 AEDT explícito |
| JPY set/2026 | 24/10/2026 00:00Z | Statistics Bureau publicou em 23/10; próximo dia UTC conservador |
| CHF out/2026 | 04/11/2026 00:00Z | FSO publicou em 03/11; próximo dia UTC conservador |
| NZD terceiro trimestre/2026 | 21/10/2026 21:45Z | Stats NZ: 22/10 10h45 NZDT explícito |

O validador `atlasquant_trader_g8_macro_asof_lab.py` recusa carimbos alegados
`published_at_utc` ou `captured_at_utc` anteriores ao respectivo limite.
Em todos os oito casos, superar o limite só significa que **a cronologia não
é obviamente impossível**: não prova valor, fonte, versão ou disponibilização
histórica, e jamais produz viés negociável.

Limites com data apenas são propositalmente posteriores ao dia informado:
podem negar um dado efetivamente divulgado na tarde anterior, mas não criam
falsa certeza de disponibilidade intradiária. Para EUR setembro, o **FLASH**
prévio não herda o piso de **FINAL** e continua insuficiente para completar
a evidência final. O **FINAL de outubro EUR** ainda não tem neste catálogo
um limite próprio; não presumir horário nem etapa.

## Fontes oficiais verificadas

- BLS set: https://www.bls.gov/news.release/archives/cpi_10142026.htm
- BLS out: https://www.bls.gov/news.release/archives/cpi_11102026.htm
- Eurostat set final: https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap
- ONS set: https://www.ons.gov.uk/releases/consumerpriceinflationukseptember2026
- Statistics Canada set: https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm
- ABS set: https://www.abs.gov.au/media-centre/media-releases/cpi-rose-43-year-september-2026
- Statistics Bureau Japan set: https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.htm
- FSO Suíça out: https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i
- Stats NZ trimestre set: https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/

As oito moedas e os 28 pares foram verificados com testes sintéticos de um
segundo antes e exatamente no limite; foram preservados `AGUARDAR`,
`trade_authorized=False`, sem HTTP, contas, MT5, worker, publicação ou custo.
