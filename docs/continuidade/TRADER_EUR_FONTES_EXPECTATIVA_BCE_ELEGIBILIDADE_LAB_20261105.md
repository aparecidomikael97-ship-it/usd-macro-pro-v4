# AtlasQuant Trader — elegibilidade de fontes de expectativas do euro (LAB)

Checkpoint 05/11/2026 UTC, continuação da PR #1815 após `7300bdcd`.
**Somente pesquisa:** sem custos, merge, publicação, Worker, cron, Radar ou
operação real. Preservadas PR #1816 e `main`.

## O que verificamos em fontes oficiais

| Fonte e conceito | Granularidade da informação | Disponibilidade pública / limitação | Decisão |
| --- | --- | --- | --- |
| [BCE SMA](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html) — expectativas de analistas | Pesquisa conduzida antes das reuniões | Resultados **agregados** publicados depois da reunião; perguntas e prazo de respostas anteriores não são consenso disponível | `POST_EVENT`, bloqueada para simulação ex-ante |
| [BCE MMSR OIS](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/money_market/html/index.en.html) — taxas de swaps spot | **Agregados por período de manutenção de reservas (MP)** | Publicação **15 dias úteis TARGET após** o fim do MP; rótulos `B`/dias úteis não significam divulgação da taxa agregada no dia | `RELEASE_LAG`, bloqueada como consenso intradiário |
| BCE MMSR OIS forward | **Agregado trimestral** | Publicação junto da divulgação posterior na frequência MP; não é preço de swap testemunhado antes de cada reunião | `RELEASE_LAG`, bloqueada |
| [BCE EMMS](https://data.ecb.europa.eu/data/datasets/EMMS/data-information) — histórico expandido do mercado monetário | Séries históricas de mercado | Atualização anual indicada na documentação; não usar como feed diário nem como vintage intradiária | `HISTORICAL`, bloqueada para gatilho |
| [BCE €STR](https://data.ecb.europa.eu/data/datasets/EST/data-information) — overnight realizado | Taxa de transações do **dia anterior** | Publicada no dia útil seguinte; mede custo realizado e **não** expectativa de política monetária | `REALIZED`, bloqueada como consenso |
| [Curvas de títulos de governos da zona do euro](https://data.ecb.europa.eu/methodology/yield-curves) | Juros futuros implícitos em **títulos soberanos** | Influenciados por outros fatores e riscos; não equivalem diretamente a OIS €STR nem a probabilidade de decisão DFR | `DIFFERENT_MEASURE`, bloqueada |

Segundo o próprio [Boletim Econômico BCE 2026](https://www.ecb.europa.eu/press/economic-bulletin/articles/2026/html/ecb.ebart202604_01~1fcadce39a.en.html),
as pesquisas privadas de Bloomberg e Thomson Reuters geralmente ficam
disponíveis na semana anterior à decisão. **Não verificamos acesso gratuito,
licença de redistribuição, captura assinada ou histórico PIT dessas fontes**.
Sem autorização de gastos, elas ficam apenas como candidatas futuras.

## Alteração implementada

O leitor offline `atlasquant_trader_eurusd_consensus_pit_lab.py`, que já
distinguia data da resposta e data de publicação da pesquisa, agora possui
cinco identificadores de medidas monetárias EUR que não podem ser promovidos
para consenso da decisão:

- `ECB_MMSR_OIS_SPOT_MP_AGGREGATE`;
- `ECB_MMSR_OIS_FORWARD_QUARTER_AGGREGATE`;
- `ECB_EMMS_OIS_ANNUAL_HISTORY`;
- `ECB_ESTR_REALIZED_OVERNIGHT`;
- `ECB_YC_SOVEREIGN_BOND_FORWARD`.

Para cada um, retorna motivo específico e **nega**
`source_measure_is_event_consensus_verified`,
`historical_point_in_time_eligible`, `pre_event_consensus_verified`,
`market_surprise_bps`, `fx_bias` e `trade_authorized`.

Os testes novos simulam inclusive alguém fornecendo uma data de publicação
**alegadamente anterior** ao evento. Um relógio plausível não transforma uma
taxa realizada ou um agregado atrasado em previsão disponível ao trader.

## Bloqueio e próximo objetivo

Até encontrar uma fonte EUR com **mesma medida/horizonte**, licença compatível,
vintage efetivamente disponível antes do anúncio e testemunho de publicação,
o AtlasQuant não calculará surpresa de juros EUR nem ranking bilateral
EUR/USD baseado nessas estatísticas. A fonte USD Atlanta Fed MPT permanece
somente pessoal/educacional e mede outra variável (média SOFR trimestral).

Próxima pesquisa: avaliar alternativas públicas com **preço OIS €STR antes
das decisões e timestamp preservado**, confrontando a licença e a data de
publicação; não contratar fontes pagas sem autorização do usuário.

**HARD NO-GO operacional.**
