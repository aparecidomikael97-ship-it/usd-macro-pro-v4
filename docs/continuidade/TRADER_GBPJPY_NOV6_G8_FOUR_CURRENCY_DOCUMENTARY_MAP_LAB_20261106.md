# AtlasQuant Trader — GBP/JPY e mapa documental de 4 moedas G8 (LAB)

Estudo retrospectivo realizado em **06/11/2026**, sem gastos, execução,
coleta automática, alteração visual, merge ou deploy. Objetivo: avançar
das referências EUR/USD para GBP/JPY, conservando os 28 pares na matriz.
**Documentos oficiais contemporâneos identificados hoje não são prova de
captura histórica imutável nem sinal de direção futura.**

## Quatro referências para GBP/JPY

| Moeda | Fam. | Valor divulgado | Período | Fonte oficial |
|---|---|---|---|---|
| GBP | Inflação | **CPI 3,5% anual** (não CPIH 3,6%) | Set/2026 | [ONS, boletim de setembro](https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/september2026) |
| JPY | Inflação | **CPI nacional 2,1% anual** (não CPI preliminar de Tóquio) | Set/2026 | [Estatísticas do Japão, resultado 23/10](https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.htm) |
| JPY | Juros | **Meta em torno de 1,25%** para taxa overnight sem garantia | Decisão 30/10 | [BoJ, declaração oficial PDF](https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf) |
| GBP | Juros | **Bank Rate 4,00%** após aumento de 0,25 p.p. | Decisão de 05/11 | [BoE, Monetary Policy Summary](https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026) |

Pontos de precisão:

- O ONS informa que o CPI de setembro foi divulgado **21/10 às 07h BST**
  (06h UTC). O CPIH, que inclui custos de moradia dos proprietários, é outro
  indicador; seus **3,6%** não substituem o CPI de **3,5%**.
- A página japonesa marca publicação do CPI nacional de setembro em **23/10**,
  sem carimbo intradiário autenticado nesta pesquisa. O gate conserva a
  referência somente a partir de **24/10 00h UTC**.
- A própria declaração do BoJ documenta divulgação em **30/10 às 12h02 JST**
  (03h02 UTC). O número **1,25%** é uma *diretriz aproximada* para overnight,
  não instrumento diretamente igual à Bank Rate britânica.
- O BoE publicou a decisão em **05/11**. Sem documento com o instante exato
  atestado neste caso, o gate usa conservadoramente **06/11 00h UTC**.
- O resultado do **CPI britânico de outubro**, previsto para **18/11**, não
  está no arquivo; tampouco o Summary of Opinions do BoJ previsto para 10/11.

O casebook fixo é
`TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json`.
Seu SHA-256, horários e valores são verificados pelo novo
`atlasquant_trader_gbpjpy_nov6_official_asof_lab.py`. É **pesquisa
retrospectiva de página**, sem arquivo original independente de cada publicação.

## Expansão para a matriz dos 28 pares

Novo `atlasquant_trader_g8_four_currency_doc_coverage_lab.py` combina os dois
casebooks (EUR/USD e GBP/JPY) **sem criar documentos para outras moedas**.

- Universo preservado: **8 moedas / 28 pares**.
- Moedas com **dois tipos de referência documental visíveis** em 06/11:
  EUR, USD, GBP e JPY (4/8), ainda sem verificação de vintage.
- Cruzamentos com referência de CPI e juros para **ambas** as moedas:
  **EUR/USD, GBP/USD, USD/JPY, EUR/GBP, EUR/JPY e GBP/JPY** (6/28).
- Os outros **22 pares** continuam sem dois conjuntos completos de referências
  nesta pesquisa; isso não quer dizer que inexistam documentos econômicos.
- Nenhum dos 28 recebe viés: `D1=AGUARDAR` e `W1=AGUARDAR`.
- A presença de referências **não prova comparabilidade dos conceitos**, nem
  que um evento tenha sido surpresa para o mercado, nem que o par reagirá em
  alguma direção. Não há ordem de força real nem Top 10 operacional.

## Bloqueios de segurança preservados

Ambos os módulos rejeitam alterações do casebook e horários simulados
anteriores aos cortes de admissão. Os campos de origem e vintage histórica
continuam `false`. A saída permanece com `fx_bias=null`,
`validated_prediction_count=0`, `validated_accuracy=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`,
`can_feed_live_radar=false`, `publishable=false`,
`worker_enabled=false`, `scheduler_enabled=false` e custo novo **R$0**.

Os **16 testes novos** usam relógios simulados e verificam GBP/JPY, cortes
de 21/10, 24/10, 30/10 e 06/11, adulterações, dados futuros, os 28 pares e
os seis cruzamentos de cobertura documental. Não avaliam acurácia de trading.

Próximo estudo: adicionar documentos de CPI e política para CHF, AUD, CAD
e NZD com a mesma cautela antes de considerar cobertura documental completa
das oito moedas. A operação real permanece **HARD NO-GO**.
