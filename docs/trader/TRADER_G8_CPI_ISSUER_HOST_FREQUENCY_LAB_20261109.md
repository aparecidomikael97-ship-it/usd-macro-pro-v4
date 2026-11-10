# AtlasQuant Trader — emissor original e frequência do CPI por moeda (LAB)

Data de referência: 09/11/2026 (America/Cuiaba). Política conservadora para dados sintéticos e declarados pelo chamador, **sem** inferência de viés.

## Lacuna corrigida

A matriz bilateral já exigia `source_type=OFFICIAL_STATISTICS_OFFICE` para CPI, mas uma página de outro país (ou de um intermediário) poderia ser declarada no recibo sem checagem de domínio. Também permitia CPI trimestral para moedas cujo indicador principal é mensal, ou mensal para NZD em 2026, sem respeitar a frequência efetiva do indicador.

## Registro G8 para CPI/HICP (referências oficiais consultadas)

| Moeda | Emissor original do indicador de inflação | Hosts aceitos para **alegação** de origem | Frequência-base LAB 2026 |
| --- | --- | --- | --- |
| USD | Bureau of Labor Statistics (BLS) | `bls.gov` | Mensal |
| EUR | Eurostat, HICP da área do euro | `ec.europa.eu`, `webgate.ec.europa.eu` (caminho `/eurostat/`) | Mensal |
| GBP | Office for National Statistics (ONS) | `ons.gov.uk` | Mensal |
| CAD | Statistics Canada | `statcan.gc.ca`, `www150.statcan.gc.ca` | Mensal |
| AUD | Australian Bureau of Statistics (ABS) | `abs.gov.au` | Mensal |
| JPY | Statistics Bureau of Japan | `stat.go.jp` | Mensal |
| CHF | Federal Statistical Office (FSO) | `bfs.admin.ch` | Mensal |
| NZD | Statistics New Zealand (Stats NZ) | `stats.govt.nz` | Trimestral |

Hosts `www.` correspondentes, explicitamente registrados no código, também são aceitos. Fontes primárias de referência: [BLS CPI](https://www.bls.gov/cpi/home.htm), [Eurostat HICP](https://ec.europa.eu/eurostat/web/hicp/information-data), [ONS](https://www.ons.gov.uk/economy/inflationandpriceindices), [Statistics Canada](https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/consumer_price_indexes), [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia), [Japan Statistics Bureau](https://www.stat.go.jp/english/data/cpi/index.htm), [FSO](https://www.bfs.admin.ch/en/press-releases) e [Stats NZ](https://www.stats.govt.nz/indicators/consumers-price-index-cpi/).

**Mudança futura conhecida:** a Stats NZ anuncia CPI mensal a partir de 2027 **além** do trimestral. O LAB mantém a frequência mensal NZD bloqueada até receber prova do primeiro lançamento, série/método e versão aplicável; o registro de 2026 **não é configuração eterna**. A ABS já apresenta CPI mensal em 2026 (não confundir com o antigo indicador mensal parcial).

## Comportamento implementado

- Campo opcional `source_url` no recibo legado; **obrigatório** para CPI com `publication_stage=FLASH` ou `FINAL`. É apenas uma alegação não autenticada do chamador.
- URL HTTPS com host estritamente pertencente à moeda, sem credencial embutida, porta explícita, fragmento, barra invertida ou domínio mascarado. EUR exige caminho `/eurostat/`. O código não faz requisição HTTP, segue redirecionamento nem valida certificado; rejeitar URLs malformadas não prova origem real.
- URL atribuída a CPI não é admissível como fonte de decisão de juros, cujo emissor deve ser o banco central.
- Frequência CPI 2026: mensal para USD/EUR/GBP/CAD/AUD/JPY/CHF; trimestral para NZD. Periodicidade errada bloqueia a linha; o bloqueio se propaga aos **sete cruzamentos** de cada moeda na matriz dos 28 pares.
- Valores, hashes, horários e tipagem de evento ainda são declarações do chamador, sem prova de bytes originais, primeira publicação ou histórico point-in-time.
- No resultado de cobertura, `issuer_host_claim` expõe só o host alegado e `issuer_host_independently_verified=False`. Nenhum valor de CPI entra como força direcional, probabilidade, ordem ou alerta.

## Validação local

Comando:

`python -m unittest -q test_atlasquant_trader_g8_macro_asof_lab test_atlasquant_trader_g8_macro_matrix_pit_lab test_atlasquant_trader_g8_event_relevance_lab test_atlasquant_trader_g8_issuer_custody_chain_lab`

**106/106 testes PASS**, nesta rodada somente sintéticos. Casos adicionados: oito hosts, falsificação de domínio, URL com usuário/porta/http, host de país errado, estágio CPI sem URL, URL CPI indevida para juros, CPI NZD mensal e CPI USD trimestral, e propagação por sete pares. Sem execução no AM12/MT5 nem teste remoto de disponibilidade de fonte.

## Próxima barreira P0

Registrar a URL **exata do comunicado**, bytes coletados e hash, carimbo independente de captura, horário original verificável da publicação, período, `FLASH/FINAL/REVISION`, série e unidade. Fazer a junção com a decisão D1/W1/MN1 apenas após certificado point-in-time. Até lá: `operational_bias=AGUARDAR`, sem deploy, merge, agendamento, worker, cobrança ou operação.
