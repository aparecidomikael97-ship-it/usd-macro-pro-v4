# Trader — caso documental Fed/BCE e catalisadores dos EUA (LAB, 02/11/2026)

## Por que este caso existe

Para antecipar o movimento, o Radar precisa saber **o que o mercado poderia esperar antes de cada notícia**, distinguir isso de **o que foi realmente publicado**, e impedir que uma informação posterior entre na previsão passada. Este caso recolhe fatos de **documentos oficiais** para testar as etiquetas e relógios. **Não é captura histórica independente nem viés de compra/venda.**

Dados em `TRADER_US_EUR_DOCUMENTED_MACRO_CASEBOOK_LAB_20261102.json`, auditados estruturalmente por `atlasquant_trader_documented_macro_casebook_lab.py`. Apenas **USD e EUR** neste piloto documental; não representa cobertura empírica das oito moedas, 28 FX ou índices.

## Cinco eventos e relógios

| Evento | Referência e contexto | Horário UTC | Situação no estudo de 02/11 |
|---|---|---|---|
| CPI EUA setembro | Documento BLS (USDL-26-1574): **3,7% a/a NSA**, **0,6% m/m SA** | 14/10, 12:30 (8h30 EDT) | Resultado histórico publicado; consenso da época ausente |
| Fed FOMC | 28/10: **manteve 3,75–4,00%** | 28/10, 18:00 (14h EDT) | Decisão publicada; expectativa pré-decisão ainda não autenticada |
| BCE | 29/10: **manteve** depósito 2,50%, refinanciamento 2,65%, marginal 2,90% | Hora exata da publicação **desconhecida** | A coletiva das 14h45 CET não substitui o horário de publicação |
| Emprego EUA outubro (Employment Situation) | Calendário BLS | **06/11, 13:30** (8h30 EST) | Evento futuro; actual e consenso **nulos** |
| CPI EUA outubro | Calendário BLS | **10/11, 13:30** (8h30 EST) | Evento futuro; actual e consenso **nulos** |

Links primários: [CPI BLS 14/10](https://www.bls.gov/news.release/archives/cpi_10142026.htm), [Fed 28/10](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm), [BCE 29/10](https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html), [BLS novembro](https://www.bls.gov/schedule/2026/11_sched_list.htm), [BLS CPI calendário](https://www.bls.gov/schedule/news_release/cpi.htm).

Horários BLS estão em **Eastern Time**, que muda com horário de verão. Por isso, **14/10 EDT = UTC−4**, enquanto **06/11 e 10/11 EST = UTC−5**. A apresentação do evento não pode reutilizar sempre o mesmo deslocamento.

## Cenários a investigar (não previsões)

- **USD versus EUR — decisão D1:** antes de NFP/CPI, verificar expectativas de emprego, inflação, juros implícitos de mercado, Fed/BCE, riscos geopolíticos e possibilidade de surpresa. **Taxa do Fed (faixa)** e **facilidade de depósito do BCE** não são instrumentos idênticos nem um sinal automático de EUR/USD.
- **NFP acima do consenso:** pode elevar a expectativa de política restritiva e apoiar USD **se** juros implícitos responderem; se o risco dominante for recessão/geopolítica, a transmissão pode mudar. Sem consenso com carimbo pré-publicação, somente `AGUARDAR`.
- **CPI acima do consenso:** pode pressionar juros e índices, mas a composição (energia, núcleo, serviços), posicionamento e reação da curva importam. Sem observação prévia, não atribuir seta de alta/baixa.
- **D1/W1/MN1:** eventos afetam horizontes de forma diferente. Uma semana de calendário pesado pode tornar o D1 incerto, ainda que o regime monetário mensal continue estável.
- **Índices:** necessitam análise própria de lucros, duration, valuation, condições financeiras, commodities e risco, além do Fed. Não herdar automaticamente a direção do USD.

A meta de alta probabilidade depende de validação histórica **walk-forward OOS**. Pontuação de força, diferença de taxas, contagem de notícias ou narrativa econômica não são probabilidade calibrada. **90% não comprovados**.

## Segurança dos fatos no tempo

Pesquisa feita no **dia 02/11**, sem recibo preciso intradiário. O inspetor só permite exibir o material a partir de **03/11 00:00 UTC** por conservadorismo. Um backtest emitido em outubro é recusado: não podemos alegar que essa pesquisa posterior foi capturada naquela data. Quando 06/11 ou 10/11 passarem, a linha de calendário irá para **PAST_DUE_NEW_RELEASE_REQUIRED**, jamais vira automaticamente dado realizado.

Mesmo após o corte de pesquisa: `real_historical_receipt_attested=false`, `event_specific_consensus_verified=false`, `actual_vs_expected_surprise_computed=false`, `market_impact_direction=UNDETERMINED`, `can_feed_live_radar=false`.

## Próximo bloqueio objetivo

Provar para cada evento, com fornecedor licenciado/permite utilização, **série e unidade**, consenso **capturado antes**, valor divulgado **depois**, revisão/vintage, horário de recebimento comprovado e preços históricos independentes. Só então ligar a hipóteses relativas das oito moedas e medir resposta do mercado.

**PR #1803: DRAFT / LAB / HARD NO-GO.** Sem API paga, sem Worker, cron, ordens, merge, deploy ou mudança do visual aprovado.
