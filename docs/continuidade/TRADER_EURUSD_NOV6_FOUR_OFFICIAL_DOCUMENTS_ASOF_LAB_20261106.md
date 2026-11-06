# AtlasQuant Trader — EUR/USD: quatro documentos oficiais com corte temporal (LAB)

Pesquisa retrospectiva em **06/11/2026**. Objetivo: impedir que a leitura macro
**use números ainda não divulgados ou compare metodologias distintas**. O piloto
cobre somente EUR/USD; não cria ranking das oito moedas nem viés dos 28 pares.
O casebook está em `TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json`.

## Referências documentais conferidas em páginas oficiais

| Moeda | Indicador | Período | Número informado | Documento |
|---|---|---|---|---|
| USD | CPI-U geral, 12 meses, não ajustado | Setembro/2026 | **3,7%** | [BLS, divulgação 14/10](https://www.bls.gov/news.release/archives/cpi_10142026.htm) |
| USD | Faixa-alvo do federal funds rate | Decisão 28/10/2026 | **3,75%–4,00%** | [Fed, comunicado 28/10](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm) |
| EUR | Taxa da facilidade de depósito do BCE | Decisão 29/10/2026 | **2,50%** | [BCE, decisão monetária](https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html) |
| EUR | HICP anual, estimativa preliminar | Outubro/2026 | **4,0% (estimativa)** | [Eurostat, comunicado 04/11](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04112026-ap) |

**Não se pode subtrair 4,0 − 3,7 para prever EUR/USD.** HICP europeu é uma
estimativa rápida de outubro; CPI-U americano é dado publicado de setembro e
usa método estatístico diferente. A taxa de depósito do BCE **não é** o
mesmo instrumento da faixa-alvo do Fed. Número maior não determina qual moeda
ficará mais forte.

## Disponibilidade temporal sem antecipar o futuro

O módulo `atlasquant_trader_eurusd_nov6_official_asof_lab.py` usa um relógio
de pesquisa **simulado** e só expõe registros após estes cortes UTC:

| Registro | Corte UTC | Justificativa |
|---|---|---|
| BLS CPI setembro | 14/10 12h30 | Embargo oficial 08h30 ET, em EDT |
| Fed decisão outubro | 28/10 18h00 | Comunicado 14h EDT |
| BCE decisão outubro | 30/10 00h00 | Dia seguinte à data do documento, conservador |
| Eurostat HICP outubro | 05/11 00h00 | Dia seguinte à data do comunicado, conservador |

Esses são **limiares estruturais**, não timestamps de captura histórica
atestados. Para BCE e Eurostat, usa-se o dia seguinte para não inventar a
hora exata de publicação. Documentos atuais podem ter sido revisados;
não temos originais históricos imutáveis com recibo de servidor.

### Dado futuro proibido

O BLS informa que o **CPI americano de outubro/2026** será publicado em
**10/11/2026 às 08h30 ET (13h30 UTC)**. Na janela de decisão de domingo,
08/11, **esse número ainda não está disponível**. O casebook não inclui o
resultado futuro, mesmo quando a inspeção simulada ocorre após 10/11.

O Eurostat classifica a observação de outubro como **flash estimate**, não
como valor definitivo; a divulgação completa foi anunciada para 18/11.

## Auditoria automatizada — somente laboratório

- Exige SHA-256 exato do casebook, esquema, famílias e indicadores. Não aceita
  reescrita silenciosa de valores, datas, URLs ou períodos.
- Esconde registros até passar seu corte de admissibilidade; datas anteriores
  não podem consultar números futuros pelo resultado do validador.
- Mantém `inflation_observation_periods_match=false`,
  `inflation_statistical_methods_comparable=false` e
  `policy_rate_instruments_directly_comparable=false`.
- Não consulta rede, não lê preço de corretora, não conhece consenso anterior
  à divulgação e **não calcula viés, surpresa, força relativa ou acerto**.

Mesmo com quatro documentos visíveis: `source_original_bytes_independently_archived=false`,
`independent_historical_page_timestamp_witnessed=false`,
`pre_event_consensus_available_and_attested=false`,
`historical_macroeconomic_vintage_attested=false`,
`fx_bias=null`, `validated_prediction_count=0`, `validated_accuracy=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`,
`can_feed_live_radar=false`, `publishable=false`,
`worker_enabled=false`, `scheduler_enabled=false`, custo novo `R$0`.

**Limite:** esta pesquisa não comprova qual era o conteúdo da página na hora
de uma previsão antiga nem demonstra que o modelo sabe converter indicadores
em direção. Faltam origem arquivada, versão histórica, consenso pré-evento,
modelo calibrado e preços futuros independentes. Os testes são de
integridade e cronologia, não de assertividade.

Próximo passo: aplicar as mesmas regras de publicação e comparabilidade às
demais seis moedas, antes de aceitar números na matriz G8.
