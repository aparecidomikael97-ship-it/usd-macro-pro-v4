# AtlasQuant Trader — EUR/USD: inflação real de setembro/2026, com datas (LAB)

**Pesquisa de 06/11/2026. Valores transcritos de publicações oficiais; não de respostas de API.**

## Observações confirmadas nas páginas oficiais

| Campo | USD — BLS CPI-U, *all items* | EUR — Eurostat HICP, área do euro EA21 |
|---|---|---|
| Setembro/2026, taxa anual | **3,7%** | **3,8%** |
| Agosto/2026, taxa anual | 3,4% | 3,2% |
| Variação da taxa anual de agosto para setembro | **+0,3 pp** | **+0,6 pp** |
| Publicação oficial do dado de setembro | 14/10/2026 | 16/10/2026 |
| Primeiro instante conservador admitido neste LAB | **15/10 00:00 UTC** | **17/10 00:00 UTC** |
| Fonte | [BLS — release arquivado USDL-26-1574](https://www.bls.gov/news.release/archives/cpi_10142026.htm) | [Eurostat — setembro de 2026, dados completos](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap) |

A fonte BLS diz explicitamente que o **CPI-U anual de 3,7% não é ajustado
sazonalmente**. A fonte Eurostat define inflação anual HICP e confirma a
composição EA21 a partir de janeiro/2026. Não são índices idênticos em
cobertura e metodologia. A variação em *pontos percentuais* acima é apenas
`taxa_anual_setembro − taxa_anual_agosto` **dentro de cada índice**, não uma
comparação de força cambial.

O `flash` de setembro da Eurostat saiu em **02/10/2026**, também de 3,8%,
mas **não é a mesma publicação** que o conjunto completo de 16/10. O ensaio
atual registra somente as publicações completas selecionadas. Da mesma
forma, o `flash` de outubro/2026 não vira automaticamente HICP completo.

## Proteção contra conhecimento do futuro

O módulo `atlasquant_trader_eurusd_sep2026_official_headline_lab.py` usa um
registro JSON transcrito e fixado por SHA-256; não baixa nada. Para uma
consulta retrospectiva:

- Antes de **15/10/2026 00:00 UTC**, não admite nenhum dos dois números
  *completos* de setembro nesse caso.
- A partir de **15/10 00:00 UTC**, admite só USD; não compara com HICP
  completo de setembro ainda não divulgado.
- A partir de **17/10 00:00 UTC**, admite as duas referências de setembro,
  mas apenas como **contexto documental**.

Os pisos posteriores aos respectivos dias oficiais são **conservadores**:
não afirmam conhecer a hora exata da primeira disponibilização da página.
O BLS registra o embargo de 08h30 ET em 14/10; o laboratório usa 15/10 UTC
para não depender de cálculos de fuso nos testes históricos. A Eurostat
registra 16/10 como a data de divulgação, sem que tenhamos um recibo de
HTTP original do instante de publicação.

## O que ainda NÃO está validado

O SHA verifica somente a **integridade do nosso próprio registro**. Os
bytes originais das páginas em suas datas de divulgação não foram
arquivados nesta sessão. Um site oficial visto retrospectivamente não é
uma prova independente de que o mesmo conteúdo estava disponível em cada
segundo do passado. Também não foi obtida uma resposta oficial da API,
nem um histórico completo de versões, consenso pré-divulgação ou reação
de taxas de juros/mercado à surpresa.

Mesmo a diferença de **0,1 pp** entre as duas taxas anuais não deve virar
um indicador automático de compra do EUR/USD: CPI-U e HICP diferem na
metodologia e expectativas monetárias podem dominar o resultado.

**Estado:** `LAB_SAME_SEP2026_PERIOD_DOCUMENTARY_HEADLINE_CONTEXT_ONLY`
após o piso de 17/10; `AGUARDAR` no viés D1/W1, zero previsões validadas,
acurácia desconhecida, nenhuma publicação, merge, Worker, agendamento,
transação, cobrança nova ou alteração da interface aprovada.
