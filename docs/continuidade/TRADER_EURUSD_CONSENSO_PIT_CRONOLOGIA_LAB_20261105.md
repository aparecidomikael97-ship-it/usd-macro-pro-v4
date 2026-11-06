# AtlasQuant Trader — auditoria cronológica do consenso BCE/Fed (LAB)

Checkpoint 05/11/2026 UTC; continuidade da PR #1815 após o commit `3b21c776`.
**Sem merge, publicação, Worker, cron, custo novo ou operação real.**

## Achado fundamental: a pesquisa pode ser pré-reunião, mas pública só depois

- O [BCE — Survey of Monetary Analysts (SMA)](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html)
  informa que os questionários são enviados antes da reunião, enquanto a
  **publicação agregada** é posterior. O calendário de 2026 é **tentativo**:
  a página em inglês consultada indicava reunião em **29/10** e divulgação
  agregada prevista para **30/10**. Uma [versão localizada em estoniano](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.et.html)
  indicava **02/11**. Há discrepância entre versões; nenhuma é testemunho
  da publicação efetiva. Ambas as datas previstas são **posteriores** à decisão.
- No Fed de Nova York, a [Survey of Market Expectations (SME)](https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations)
  passou a combinar, em **2025**, as antigas pesquisas de *Primary Dealers*
  e *Market Participants*. O banco informa que publica as **perguntas**
  antes de cada FOMC, mas os **resultados agregados** aproximadamente três
  semanas depois; não são consenso público pré-evento para backtest de
  decisão intradiária. A [página do próprio Fed NY](https://www.newyorkfed.org/markets/data-hub)
  também descreve publicação posterior às atas da reunião.

**Consequência:** usar em M15 uma resposta pré-evento que só se tornou
publicamente conhecida após o anúncio seria **vazamento do futuro** no
backtest. A data de envio das perguntas e o encerramento de respostas não
autorizam o uso das respostas agregadas naquele dia.

## Novo gate offline

O módulo `atlasquant_trader_eurusd_consensus_pit_lab.py` audita metadados
fornecidos pelo chamador e os bytes de uma eventual evidência, sem download:

1. identidade da fonte (`ECB_SMA_AGGREGATE`, `NYFED_SME_AGGREGATE`,
   `NYFED_SPD_AGGREGATE_LEGACY` ou fonte **independente candidata**), moeda,
   dia do evento, relógio UTC, data/horário alegados de publicação e captura;
2. impede publicação posterior à captura, data de disponibilização posterior
   ao evento, encerramento da pesquisa após a publicação, dados futuros e
   horários sem fuso; exige documento bruto limitado a 256 KiB, com SHA-256;
3. bloqueia todas as agregações oficiais conhecidas por divulgar depois da
   reunião, mesmo se um chamador alegar horário antecipado;
4. marca como apenas `LAB_PRE_EVENT_CHRONOLOGY_PLAUSIBLE_UNVERIFIED` uma
   eventual fonte independente **alegadamente** capturada e publicada antes.
   Horário alegado e hash **não comprovam** publicamente a fonte, o instante
   do anúncio, direito de uso nem integridade de uma vintage histórica;
5. datas **no mesmo dia** do evento ficam bloqueadas: não há testemunho
   independente do instante exato do anúncio e não se inventa esse horário;
6. a comparação EUR/USD também nunca produz `market_surprise_bps` ou `fx_bias`.

**Nenhum caminho deste módulo retorna `pre_event_consensus_verified=true`,
`historical_point_in_time_eligible=true` ou `trade_authorized=true`.**
O estado operacional permanece `AGUARDAR`. Nenhum valor de consenso real foi
adquirido, importado ou inventado nesta etapa.

## Exemplos de bloqueio

| Caso sintético/documental | Resultado exigido |
| --- | --- |
| BCE SMA: reunião 29/10, publicação **prevista** 30/10 | `DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE` |
| NY Fed SME: divulgação agregada somente após a reunião | `DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE` ou bloqueio pela prática conhecida da fonte |
| Questões de pesquisa distribuídas antes da reunião | Não são respostas agregadas; fonte de consenso inválida |
| Fonte externa com publicação e captura alegadas no próprio dia | `SAME_DAY_ORDER_NEEDS_WITNESSED_EVENT_TIME` |
| Documento capturado depois da reunião | `DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE` |
| Fonte externa alegadamente publicada e capturada em dias anteriores | Cronologia *plausível*, mas prova PIT e viés **bloqueados** |

`test_atlasquant_trader_eurusd_consensus_pit_lab.py` contém 19 testes
determinísticos sintéticos e está integrado à Quality CI. A bateria focada
EUR/USD (oito módulos) foi executada localmente com **145 PASS**.

## Próxima prova requerida (não realizada)

Buscar um material de expectativa **realmente disponível antes da decisão**,
com direitos de uso e evidência temporal independente, medindo exatamente
o mesmo instrumento e horizonte da decisão. Só então confrontar o comunicado
oficial datado, uma testemunha do momento de divulgação e preços spot FX
independentes numa validação histórica ponto-no-tempo e fora da amostra.

**HARD NO-GO — investigação e testes apenas.**
