# Trader — inflação oficial das oito moedas, com guarda ponto-no-tempo (LAB, 03/11/2026)

## Finalidade
A prioridade do AtlasQuant Trader é **viés macro antecipatório D1/W1/MN1 para 28 pares Forex e índices**. Esta camada registra a inflação anual **já publicada** por órgão estatístico de cada economia e explicita diferenças de método, periodicidade e divulgação. Não é um forecast, ranking de moeda forte nem medida de probabilidade.

## Evidências públicas antes de 03/11
| Moeda | Leitura anual publicada | Período | Publicação | Série e órgão |
|---|---:|---|---|---|
| USD | 3,7% | setembro mensal | 14/10/2026 | BLS **CPI-U cheio, não ajustado** [arquivo](https://www.bls.gov/news.release/archives/cpi_10142026.htm) |
| EUR | 3,8% | setembro mensal | 16/10/2026 | Eurostat **HICP área do euro, final** [arquivo](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap) |
| GBP | 3,5% | setembro mensal | 21/10/2026 | ONS **CPI, não CPIH de 3,6%** [boletim](https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026) |
| JPY | 2,1% | setembro mensal | 23/10/2026 | Statistics Bureau **CPI nacional cheio, base 2025** [página](https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html) / [PDF do levantamento consultado](https://www.stat.go.jp/data/cpi/sokuhou/tsuki/pdf/zenkoku.pdf) |
| CHF | 1,0% | setembro mensal | 01/10/2026 | Escritório Federal de Estatística **CPI cheio** [arquivo](https://www.bfs.admin.ch/en/newnsb/wNfni1DvzKuQ) |
| CAD | 3,1% | setembro mensal | 19/10/2026 | Statistics Canada **CPI cheio** [arquivo](https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm) |
| AUD | 4,3% | setembro mensal | 28/10/2026 | ABS **CPI cheio mensal** [arquivo](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026) |
| NZD | 3,7% | **trimestre encerrado em setembro** | 22/10/2026 | Stats NZ **CPI cheio trimestral**, variação de 12 meses [arquivo](https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/) |

**Atualização Suíça:** o órgão estatístico publicou em **03/11/2026** CPI de outubro a **1,5% em 12 meses** [fonte oficial](https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i). Como não há hora/captura independente comprovada, o novo número entra neste LAB somente **a partir de 04/11 às 00h UTC**. Uma consulta histórica feita ainda em 03/11 não recebe retrospectivamente o 1,5%. Isso é deliberadamente conservador.

**Calendário EUR:** a Eurostat marcou a próxima **estimativa preliminar HICP de outubro para 04/11**. A partir dessa data, o valor final de setembro continua citado como histórico, mas recebe `NEW_RELEASE_DAY_REVIEW_REQUIRED`, sem se promover como último dado atualizado.

## Contrato implementado
`atlasquant_trader_g8_inflation_documentary_lab.py` protege nove versões documentais (oito moedas + segunda edição CHF), com:
- esquema exato, fonte oficial e valor publicado amarrados a cada entrada — alterações e campos extras são rejeitados;
- **corte UTC conservador no dia seguinte à publicação** quando só a data é conhecida, sem presumir a hora real;
- 28 pares com referência às moedas base/cotada, sempre `bias=AGUARDAR` e `probability_calibrated=None`;
- `numeric_inflation_gap_pp=None`, pois mesmo leituras anuais de CPI/HICP usam definições nacionais distintas e a periodicidade NZD é trimestral;
- indicadores negativos `independent_receipt_verified=false`, `consensus_pre_event_verified=false`, `forward_policy_path_verified=false`, `real_oos_accuracy_proven=false`, `can_feed_live_radar=false`.

Os links Japan `index-z.html` e `zenkoku.pdf` são páginas/arquivos apontados como últimas publicações e **podem mudar com a próxima divulgação**. O conteúdo original e seu SHA independente NÃO foram arquivados nem homologados. Todas as leituras são **transcrições documentais manuais**, não fonte automática de produção. Publicação e revisão futuras podem exigir novas versões.

## O que falta para viés antecipatório verdadeiro
- Emprego, atividade, juros futuros/curvas e macro geopolítico comparável dos oito blocos;
- última leitura **versus consenso que existia antes da notícia**, com procedência verificável;
- provável mecanismo causal (inflação pode aumentar expectativa de juros, mas também prejudicar crescimento, e a cotação pode já ter precificado tudo);
- backtest walk-forward D1/W1/MN1 com preços independentes, custos/abstenção e calibração, antes de qualquer meta de 90%.

**LAB / HARD NO-GO:** sem Worker, scheduler, UI, ordens, API paga, deploy, merge ou custo novo. Testes do arquivo `test_atlasquant_trader_g8_inflation_documentary_lab.py` anexados ao Quality CI.
