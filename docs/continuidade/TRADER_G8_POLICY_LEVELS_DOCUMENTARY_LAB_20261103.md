# AtlasQuant Trader — decisões oficiais dos oito bancos centrais (LAB 03/11/2026)

## Objetivo
Ampliar a leitura macro fundamental do Trader do piloto USD/GBP para **oito moedas/28 pares**, preservando horizonte ponto-no-tempo e dados oficiais anteriores à decisão de viés. Esta é uma **base documental de níveis anunciados**, não força cambial, consenso de futuros juros, recomendação ou teste de assertividade.

## Dados transcritos da fonte primária
| Moeda | Instrumento específico | Nível anunciado | Decisão | Fonte |
|---|---|---:|---|---|
| USD | Fed funds **target range** | 3,75–4,00% | 28/10 | [FOMC](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm) |
| EUR | Taxa de depósito BCE | 2,50% | 29/10 | [BCE](https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html) |
| GBP | Bank Rate | 3,75% | 17/09 | [BoE](https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/september-2026) |
| JPY | Diretriz para juro overnight, **aproximada** | cerca de 1,25% | 30/10 | [BoJ — PDF](https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf) |
| CHF | SNB policy rate | 0,00% | 24/09 | [SNB](https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924) |
| CAD | Target overnight rate | 2,50% | 28/10 | [BoC](https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/) |
| AUD | Cash rate target | **4,60% até anúncio de 03/11; 4,85% após anúncio** | 29/09 e 03/11 | [RBA setembro](https://www.rba.gov.au/media-releases/2026/mr-26-27.html); [RBA novembro](https://www.rba.gov.au/media-releases/2026/mr-26-30.html) |
| NZD | Official cash rate | 2,75% | 28/10 | [RBNZ](https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent) |

**Importante sobre AUD:** a RBA anunciou às **14h30 AEDT de 03/11** (03h30 UTC) a elevação de 4,60% para 4,85%, com **data efetiva local 04/11**. O LAB usa gate conservador **03h31 UTC** (um minuto após a hora programada; **não** é atestado de captura), com três estados:
- até 03h30 UTC inclusive: só a **decisão anterior de 4,60%** é devolvida;
- entre 03h31 e o início da data local de 04/11: **4,85% anunciada**, ainda com data efetiva futura;
- após atingir 04/11 na Austrália: **data efetiva alcançada**, sem alegar que as operações já ajustaram precisamente à meia-noite.

**GBP:** o calendário oficial marca 05/11 como nova decisão. A partir desse dia o módulo não afirma que 3,75% ainda é o valor atual: pede atualização oficial. Esse bloqueio é conservador, mesmo antes do horário efetivo da reunião.

As publicações sem horário exato autenticado são elegíveis **somente a partir de 00h UTC do dia seguinte à decisão**, evitando inferir a hora de publicação. Não há arquivo de bytes originais, recebimento/captura assinada, API, licença de ingestão homologada ou atualização online: são valores documentais manualmente transcritos.

## Código, contrato e limite de interpretação
`atlasquant_trader_g8_policy_documentary_lab.py`: nove versões documentais para oito moedas (AUD tem duas), mais 28 linhas canônicas, com abstenção explícita:
- USD é uma faixa, não uma taxa única; BoJ é diretriz aproximada; BCE, BoE, SNB, BoC, RBA e RBNZ têm alvos de natureza institucional distinta.
- **Não** calcular diferença nominal de juros como força relativa entre moedas sem período/riscos/base comparáveis e expectativa de trajetória futura.
- `nominal_policy_rate_gap_pp=None`, `future_policy_expectation_gap_pp=None`, `bias=AGUARDAR` e `probability_calibrated=None` nos 28 pares.
- `source_receipts_independently_attested=false`, `market_priced_expectations_verified=false`, `fx_direction_proven=false`, `accuracy_90_proven=false`, `can_feed_live_radar=false`, `trade_authorized=false`.

Os testes atacam principalmente vazamento da decisão RBA de 03/11 para análise realizada antes de 03h31 UTC, a transição anúncio/data efetiva, moeda ausente, fraude de URL, taxas adulteradas, falsa probabilidade e a recusa de direção sem dados de mercado.

## Próximas entregas com valor preditivo
1. Séries históricas ponto-no-tempo de **inflação, emprego e atividade** para oito economias, com periodicidade e revisão de cada país.
2. Expectativas de mercado publicadas **antes dos eventos**: curvas de juros prospectivos comparáveis, consensos econômicos e cenário geopolítico com fontes/licenças verificadas.
3. Hipóteses condicionais de diferenças relativas e avaliação prospectiva D1/W1/MN1 sobre **preços independentes** e amostra fora do treino. Sem 90% declarado até evidência estatística.

**LAB / HARD NO-GO:** sem custo, Worker, scheduler, contas, sinais, ordens, deploy, merge nem mudança na UI futurista aprovada.
