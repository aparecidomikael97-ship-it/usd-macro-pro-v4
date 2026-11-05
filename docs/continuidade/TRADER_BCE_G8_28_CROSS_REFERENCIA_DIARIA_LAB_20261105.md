# AtlasQuant Trader — 28 referências cruzadas G8 do BCE, 05/11/2026 (LAB)

Páginas oficiais consultadas: BCE https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html e arquivo de 04/11/2026 da Banca d'Italia https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261104/?com.dotmarketing.htmlpage.language=1.

Valores publicados em **04/11/2026**, unidades por 1 EUR: USD 1.1267, GBP 0.83460, JPY 178.30, CHF 0.9188, AUD 1.6061, CAD 1.5701, NZD 1.9988. EUR=1 por definição. A página de gráfico oficial do BCE https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html apresenta EUR/USD 1.1216 em 02/11, 1.1179 em 03/11 e 1.1267 em 04/11.

O módulo atlasquant_trader_ecb_g8_reference_day_lab.py usa esses **sete números transcritos das páginas públicas** para calcular, em Decimal, as 28 taxas cruzadas de referência, no sentido (moeda cotada/EUR) ÷ (moeda base/EUR). Exemplos **derivados**: GBP/USD 1.34998802, USD/JPY 158.24975592, AUD/NZD 1.24450532. Não são spreads, preços M15, cotações de corretora ou 28 preços observados individualmente.

**Proveniência:** nenhum arquivo XML original foi capturado. O URL https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml falhou por tipo XML não suportado no leitor web; uma segunda ferramenta retornou target_unreachable, e o ambiente local não resolveu o domínio. A Banca d'Italia replica as taxas de referência do BCE; não é um preço independente de execução. Não há SHA do XML nem comprovação de publicação histórica por instante.

**Bloqueios permanentes:** uma referência de um dia não valida viés D1/W1, força da moeda, backtest, taxa de acerto ou execução. Tudo AGUARDAR, sem Worker/Scheduler, custo novo, merge ou publicação. PR de interface #1816 preservada. Próximo passo: capturar bytes originais BCE + dados M15 de uma fonte autorizada com registros de tempo confiáveis, assim que AM12 voltar.
