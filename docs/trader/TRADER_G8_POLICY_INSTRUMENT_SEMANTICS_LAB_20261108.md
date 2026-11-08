# AtlasQuant Trader — instrumentos de juros oficiais não são equivalentes (LAB)

Pesquisa manual: **08/11/2026**. Fonte: comunicados primários de Fed, BCE,
BoE, BoC, RBA, BoJ, SNB e RBNZ. Os valores são um **retrato retrospectivo**,
não uma captura P-I-T do instante da divulgação. Conservadoramente, esta
pesquisa só pode ser referenciada após **09/11/2026 00:00 UTC**.

## Oito políticas diferentes — um erro frequente a evitar

| Moeda | Instrumento | Valor divulgado no último comunicado até 08/11 |
| --- | --- | ---: |
| USD | Faixa alvo do federal funds (Fed, 28/10) | **3,75%–4,00%** |
| EUR | Taxa da facilidade de depósitos (BCE, 29/10) | **2,50%** |
| GBP | Bank Rate (BoE, 05/11) | **4,00%** |
| CAD | Meta overnight (BoC, 28/10) | **2,50%** |
| AUD | Meta cash rate (RBA, 03/11) | **4,85%** |
| JPY | Diretriz de overnight call rate (BoJ, 30/10) | **cerca de 1,25%** |
| CHF | SNB policy rate (SNB, 24/09) | **0,00%** |
| NZD | Official Cash Rate (RBNZ, 28/10) | **2,75%** |

Exemplos concretos de cautela:

1. **Fed** anunciou um **intervalo**, que não deve ser arbitrariamente
   transformado no ponto médio e chamado de taxa única dos EUA.
2. **BoJ** usa a expressão **em torno de** 1,25% na diretriz operacional:
   não é a taxa overnight efetivamente negociada em cada momento.
3. **EUR e CAD** apresentam 2,50%, mas um é depósito no BCE e outro é meta
   overnight do BoC. Igualdade numérica não implica postura monetária igual.
4. **AUD (4,85%) versus CHF (0,00%)** não significa automaticamente comprar
   AUD/CHF. O câmbio responde às surpresas em relação ao que o mercado
   esperava, inflação e juros reais, crescimento, risco, fluxo e posicionamento.

## Fonte original de cada valor

- Fed 28/10: <https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm>
- BCE 29/10: <https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html>
- BoE 05/11: <https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026>
- BoC 28/10: <https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/>
- RBA 03/11: <https://www.rba.gov.au/media-releases/2026/mr-26-30.html>
- BoJ 30/10, PDF com diretriz aproximada: <https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf>
- SNB 24/09: <https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924>
- RBNZ 28/10: <https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent>

## O que foi implementado (somente laboratório)

- Casebook de pesquisa fixado por SHA-256:
  `docs/continuidade/TRADER_G8_POLICY_INSTRUMENT_DEFINITION_LAB_20261108.json`.
- `atlasquant_trader_g8_policy_instrument_semantics_lab.py` verifica oito
  instrumentos/decisões e seus URLs, separando **1 intervalo**, **1 diretriz
  aproximada** e **6 níveis de instrumento**.
- Mantém os valores em campos explicitamente rotulados como **alegações de
  pesquisa do emissor**, sem subtração de taxas entre moedas nem criação de
  score, probabilidade ou classificação de compra/venda.
- Os **28 pares Forex D1/W1** seguem `AGUARDAR` mesmo para pares cujos níveis
  parecem numericamente diferentes.
- Antes de 09/11/2026 00:00 UTC, recusa a pesquisa (anti-hindsight). Recusa
  alterações no casebook ou URLs, instrumento não catalogado e relógio sem fuso.

## O que falta para viés confiável

Necessários, em ordem:

1. Captura original por divulgação e versão com custódia/horário verificáveis.
2. Surpresas e **mudanças nas expectativas futuras de juros**, não apenas
   o nível divulgado. Metodologia de juros reais comparável e CPI observado
   com mesma frequência/estágio também precisam de auditoria.
3. Registro prévio de regras e janelas de análise D1/W1; validação fora da
   amostra em preços independentes, antes de chamar score de probabilidade.

Os 10 novos testes deste módulo foram aprovados. Regressão local integrada:
**345 testes, 344 PASS e 1 SKIP** do arquivo real ausente no AM12 offline.

Sem negócio real, receita projetada, merge, deploy, agendamento, Worker,
captura de conta MT5 ou cobrança. **PR #1851 permanece rascunho.**
