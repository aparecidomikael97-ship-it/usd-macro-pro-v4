# AtlasQuant Trader — oito moedas / 28 pares: cobertura DOCUMENTAL (LAB)

**Corte de pesquisa:** 06/11/2026, 17:00 UTC. **Estado:** leitura retrospectiva
de páginas oficiais; não é replay histórico autenticado, viés cambial ou sinal.

## Ampliação de quatro para oito moedas

O caso anterior já continha EUR, USD, GBP e JPY, com CPI e decisão monetária
para cada moeda. O novo casebook imutável por SHA-256 acrescenta **oito
referências** para CHF, AUD, CAD e NZD:

| Moeda | Inflação (período, divulgação, alegação da página) | Política monetária (decisão, taxa) |
|---|---|---|
| CHF | FSO CPI out/2026; 03/11; **1,5% a/a**, 0,2% m/m | SNB, 24/09: taxa de política **0,00%** |
| AUD | ABS CPI mensal set/2026; 28/10 às 11:30 AEDT; **4,3% a/a**, 0,8% m/m *original* | RBA, 03/11: *cash rate target* **4,85%**, após aumento de 25 pb |
| CAD | StatCan CPI set/2026; 19/10; **3,1% a/a**, 0,1% m/m, sem ajuste sazonal | BoC, 28/10: meta da taxa *overnight* **2,50%**, não *Bank Rate* de 2,75% |
| NZD | Stats NZ CPI **trimestral** 2026-Q3; 22/10; **3,7% a/a** (NÃO é CPI mensal de setembro) | RBNZ, 28/10: *official cash rate* **2,75%**, mantida |

Referências oficiais conferidas em 06/11:

- CHF: [FSO](https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i), [SNB](https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924).
- AUD: [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026), [RBA](https://www.rba.gov.au/media-releases/2026/mr-26-30.html).
- CAD: [StatCan](https://www150.statcan.gc.ca/n1/daily-quotidien/261019/t001a-eng.htm), [BoC](https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/).
- NZD: [Stats NZ](https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/), [RBNZ](https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent).

## Temporalidade e bloqueios

- O arquivo separado `TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json`
  fixa URL, observação, referência, tipo de taxa, alegação numérica e
  **piso de admissibilidade em UTC**. O validador somente aceita os bytes
  idênticos ao SHA-256 fixo; alterações são recusadas.
- Datas com hora clara: ABS **28/10 00:30 UTC** (11:30 AEDT), RBNZ
  **28/10 01:00 UTC** (14:00 NZDT), RBA **03/11 03:30 UTC** (14:30 AEDT).
  Isso traduz a hora publicada/programada, não prova histórica independente.
- Sem hora de divulgação verificada para o documento: piso conservador à
  **00:00 UTC no dia seguinte** ao calendário da publicação (SNB, StatCan,
  Stats NZ CPI, BoC, FSO). Nenhum resultado aparece antes do piso.
- Próximas divulgações registradas, **sem antecipação de número**: CPI mensal
  australiano de outubro em **25/11** e decisão RBNZ em **09/12**.
- Os documentos são **páginas públicas observadas retrospectivamente**. O
  hash é do casebook elaborado na pesquisa: **não autentica HTTP original,
  vintage histórico, horário de disponibilidade real ou licença de revenda**.

## Resultado da ponte documental

Em 06/11, 17:00 UTC: **16/16 referências visíveis**, **8/8 moedas** com
ambas as famílias e **28/28 cruzamentos** com documentação nos dois lados.
Isso mede apenas *presença de referência*, sem significado direcional.

**Todas as 28 linhas continuam D1 = AGUARDAR, W1 = AGUARDAR.** Inflações
mensais e trimestrais e instrumentos de juros não são comparados diretamente;
nenhum diferencial vira ranking de força. Não há consenso pré-evento verificado,
surpresa macro, retorno M15 validado, amostra de acerto, confiança de 80–90%,
paper-trade acionado ou ordem real.

Laboratório offline; **zero HTTP dentro do módulo, zero custo novo, sem
merge, deploy, Worker, agendamento, publicação ou operação.**

Próximo bloqueio técnico: capturar originais com proveniência autenticada e
horário de disponibilidade, padronizar instrumentos/frequências e medir
comparações prospectivas D1/W1 contra resultado observado fora da amostra.
