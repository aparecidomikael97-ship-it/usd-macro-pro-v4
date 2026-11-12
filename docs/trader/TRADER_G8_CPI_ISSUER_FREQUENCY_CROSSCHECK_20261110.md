# AtlasQuant Trader — fontes e cadências de CPI das oito moedas (LAB, 10/11/2026)

## O que foi conferido

As oito moedas G8 são acompanhadas por **emissores estatísticos oficiais**,
mas seus índices não são automaticamente equivalentes. Não basta subtrair
as duas taxas de inflação de um par para emitir viés.

| Moeda | Órgão e conceito | Periodicidade vigente em 2026 |
| --- | --- | --- |
| USD | BLS, CPI-U não ajustado, todos os itens | Mensal |
| EUR | Eurostat, HICP da área do euro, flash/final | Mensal |
| GBP | ONS, CPI britânico (distinguir de CPIH) | Mensal |
| CAD | Statistics Canada, CPI nacional | Mensal |
| AUD | ABS, CPI australiano completo | **Mensal** desde a referência de outubro/2025 |
| JPY | Statistics Bureau Japan, CPI nacional | Mensal (base 2025 em 2026) |
| CHF | Federal Statistical Office, CPI suíço | Mensal (base dezembro/2025 em 2026) |
| NZD | Stats NZ, CPI nacional | **Trimestral** em 2026 |

Stats NZ informa início previsto da publicação **mensal em julho de 2027**,
referente a junho/2027, **além** da trimestral, que continua sendo a medida
oficial até aviso posterior. A implementação **não muda automaticamente** a
frequência em 2027 só porque existe um anúncio prévio.

## Ajuste no código

O módulo existente `atlasquant_trader_g8_macro_matrix_pit_lab.py` passa a
identificar para cada um dos 28 pares:

- `base_cpi_publication_frequency_2026`;
- `quote_cpi_publication_frequency_2026`;
- `cpi_publication_frequency_mismatch`;
- `cpi_raw_yoy_differential_validated=false`;
- `cpi_issuer_methodologies_harmonized=false`.

**Sete** pares envolvendo NZD têm cadência de CPI mensal/trimestral
divergente; os **outros 21** têm fontes mensais, mas isso **não significa**
que os índices, as cestas, as bases ou o impacto na moeda sejam comparáveis
sem metodologia adicional. Mesmo sem nenhum recibo, a frequência estrutural
continua visível, enquanto a cobertura de dados permanece ausente.

## Validação e limites

- `python -m unittest discover -q -p 'test_atlasquant*.py'`: **198/198 OK**.
- 3 testes novos: sete pares mistos, metodologia nunca aprovada por mera
  igualdade de frequência, e frequência conhecida mesmo com recibos vazios.
- Nenhum feed atual ou vintage de indicador novo foi capturado nesta etapa.
- Sem transformação de diferença bruta de inflação em probabilidade,
  força de moeda, sinal, viés, publicação, job, custo ou operação.

## Referências oficiais consultadas

- BLS: https://www.bls.gov/cpi/news.htm
- Eurostat: https://ec.europa.eu/eurostat/web/hicp/information-data
- ONS: https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/latest
- Statistics Canada: https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/consumer_price_indexes
- ABS: https://www.abs.gov.au/statistics/detailed-methodology-information/concepts-sources-methods/consumer-price-index-concepts-sources-and-methods/2025/outputs-and-dissemination
- Statistics Bureau Japan: https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html
- Swiss FSO: https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i
- Stats NZ: https://www.stats.govt.nz/topics/moving-to-a-monthly-cpi/

Próximo gate: versionar a metodologia e base de cada série, suas revisões e
seu horário real de disponibilidade antes de calibrar direção de mercado.
