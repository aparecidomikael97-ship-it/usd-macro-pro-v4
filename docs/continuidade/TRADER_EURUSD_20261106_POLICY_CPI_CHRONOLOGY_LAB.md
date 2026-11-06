# AtlasQuant Trader — cronologia juros + inflação EUR/USD (LAB)

**06/11/2026 — provas documentais retrospectivas, não sinal e não API ao vivo.**

## Sequência econômica real

| Data da publicação oficial | Evento e nível documentado | Disponibilidade conservadora no LAB |
|---|---|---|
| **10/09** | BCE **subiu 25 pb**: taxa de depósito **2,50%**, com efeito **16/09** | **11/09 00:00 UTC** |
| **16/09** | FOMC **subiu 25 pb**: faixa-alvo **3,75%–4,00%**, com efeito **17/09** | **17/09 00:00 UTC** |
| **14/10** | BLS: CPI-U anual de setembro **3,7%**, agosto **3,4%** | **15/10 00:00 UTC** |
| **16/10** | Eurostat: HICP anual completo de setembro **3,8%**, agosto **3,2%** | **17/10 00:00 UTC** |
| **28/10** | FOMC **manteve** a faixa de **3,75%–4,00%** | **29/10 00:00 UTC** |
| **29/10** | BCE **manteve** a taxa de depósito em **2,50%** | **30/10 00:00 UTC** |

Fontes primárias:

- [BCE: decisão de 10/09](https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260910~314e508016.en.html)
- [Fed: comunicado de 16/09](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm)
- [Fed: nota de implementação de 16/09](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a1.htm)
- [BLS: CPI setembro divulgado em 14/10](https://www.bls.gov/news.release/archives/cpi_10142026.htm)
- [Eurostat: HICP setembro completo divulgado em 16/10](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap)
- [Fed: comunicado de 28/10](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm)
- [BCE: decisão de 29/10](https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html)

## Correção conceitual importante

**Decisão / anúncio ≠ data em que o novo nível passa a vigorar.**
Por exemplo, em 11/09 o novo DFR de 2,50% já havia sido anunciado, mas
ainda não estava em vigor; o sistema **não** pode descrevê-lo como nível
vigente antes de 16/09. O mesmo vale para a faixa do FOMC e 17/09.

O novo módulo
`atlasquant_trader_eurusd_sep2026_policy_inflation_timeline_lab.py`
recebe dois registros locais: o caso de inflação da revisão anterior e um
novo registro das quatro decisões monetárias. Valida hash e campos fixos,
respeita os pisos de publicação de cada documento e separa os anúncios já
conhecidos dos níveis **efetivamente vigentes**. Não executa consultas HTTP.

Exemplos de bloqueio contra conhecimento do futuro:

- **15/10:** duas decisões monetárias de setembro conhecidas, CPI de
  setembro dos EUA visível, **HICP completo de setembro ainda ausente**.
- **17/10:** ambos os CPI/HICP de setembro e as decisões de setembro
  visíveis; **decisões de fim de outubro ainda ausentes**.
- **29/10:** decisão Fed de 28/10 visível, mas **decisão BCE de 29/10
  ainda indisponível** pelo piso conservador adotado.
- **30/10 em diante:** quatro decisões visíveis em contexto, mas sem
  transformá-las em previsão EUR/USD.

## Portões que permanecem fechados

As publicações oficiais foram conferidas retrospectivamente; **os bytes
originais dos instantes históricos não foram arquivados**, nem a chegada
dos comunicados foi testemunhada por relógio externo. O SHA protege apenas
os dois registros manuais locais. O histórico diário de níveis BCE/Fed
capturado anteriormente no AM12 permanece um conjunto **separado e em
quarentena**; não há novo download nem cópia dos ZIPs privados.

Ainda faltam: expectativas ex-ante dos juros e do CPI, surpresa medida
contra o consenso, taxas comparáveis, reação do preço independente,
backtest fora da amostra e governança de publicação. A taxa de depósito
do BCE e a faixa do Fed têm instrumentos distintos: **nunca apresentar
o diferencial numérico como fator de compra/venda**.

**D1/W1 nos 28 pares: `AGUARDAR`.** Sem previsões validadas, acurácia
medida, ordem, merge, deploy, Worker, agendamento, UI publicada ou custo novo.
