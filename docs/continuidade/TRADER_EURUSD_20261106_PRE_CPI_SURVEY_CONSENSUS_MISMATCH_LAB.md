# AtlasQuant Trader — duas expectativas reais que NÃO são surpresa do CPI

**06/11/2026 — novo experimento LAB, somente documentos e cálculo de elegibilidade.**

## Fontes verificadas

| Candidato disponível antes do CPI completo de setembro | Valor | O que significa de fato |
|---|---:|---|
| [Fed de Nova York, SCE de setembro, publicado em 07/10](https://www.newyorkfed.org/newsevents/news/research/2026/20261007.html) | **3,9%** | Mediana da inflação **esperada pelas famílias para 12 meses à frente**, não previsão do CPI-U de setembro/2026 |
| [BCE, SMA de setembro, resultados agregados de 11/09](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html) | **3,2%** | Mediana de 69 respostas de analistas para **HICP do trimestre 2026Q3**, variação anual; não previsão da observação mensal de setembro |

Para o valor do BCE, ver tabela **“Median expected HICP inflation rates”,
linha `2026Q3`**, no [PDF oficial](https://www.ecb.europa.eu/stats/ecb_surveys/sma/shared/pdf/ecb.smar260911_september.en.pdf).
O [calendário oficial da pesquisa SMA](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html)
confirma a publicação agregada **em 11/09**, **após** a decisão BCE de
10/09. O questionário e prazo de envio não equivalem à divulgação pública
de um número consensual: os resultados agregados não podem ser retroagidos
para prever a decisão BCE anterior.

## Erros específicos evitados

Dois cálculos que **parecem** surpresas, mas seriam tecnicamente falsos:

1. CPI-U dos EUA setembro **3,7%** menos SCE **3,9%** = **-0,2 pp**.
   Rejeitado: domicílios estimaram a inflação dos próximos 12 meses, não
   o número publicado de setembro.
2. HICP zona do euro setembro **3,8%** menos SMA trimestral **3,2%** =
   **+0,6 pp**. Rejeitado: mediana trimestral não é consenso para o
   resultado mensal de setembro.

Ambas as pesquisas foram divulgadas antes dos respectivos CPI/HICP
completos, mas **“antes” não basta**: é necessário casar *mesmo indicador,
período, horizonte, transformação, calendário e população relevante de
expectativa*. As páginas oficiais não entregam aqui o consenso de mercado
para a divulgação **exata**. A identificação desse consenso ainda está
pendente e não deve ser substituída por opinião ou número pós-evento.

## Portões executados

O módulo `atlasquant_trader_eurusd_sep2026_expectations_mismatch_lab.py`
combina os casos manuais, com hash, ao laboratório de cronologia juros/CPI:

- **12/09 UTC:** aparece somente o agregado SMA, sem tratá-lo como
  expectativa pré-decisão do BCE de 10/09.
- **08/10 UTC:** aparece também a pesquisa SCE de 07/10; nenhum CPI de
  setembro completo ainda aparece neste recorte.
- **15/10 UTC:** CPI dos EUA de setembro está visível, mas **nenhum valor
  de surpresa** é calculado a partir da pesquisa SCE.
- **17/10 UTC:** também aparece HICP completo de setembro, mas a SMA
  trimestral **não** vira consenso da divulgação mensal.

Essas datas são pisos conservadores a partir de **calendários públicos
retrospectivos**; não são provas independentes do instante original de
divulgação. O SHA confere os bytes dos nossos próprios registros, não os
PDFs originais arquivados naquele dia. Não foi efetuado download de API.

**Todos os resultados:** consenso do evento `null`/ausente; surpresa
`null`/ausente; viés `AGUARDAR`; 0 previsões validadas, acurácia **não
calculada** (não se interpreta como taxa de acerto zero), sem publicação,
merge, deploy, Worker, agendamento, operação ou custo novo.
