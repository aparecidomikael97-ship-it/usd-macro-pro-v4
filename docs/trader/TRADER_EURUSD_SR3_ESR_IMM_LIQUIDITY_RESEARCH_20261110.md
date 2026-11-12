# AtlasQuant Trader — pesquisa de liquidez e trimestre IMM SR3/ESR (10/11/2026)

**Status: laboratório somente.** Sem contratação, sem coleta automática de cotações, sem uso do MT5, sem operações e sem viés. Nova atualização da PR de laboratório #1851.

## Verificação documental em fontes primárias

1. A [CME descreve SR3/ESR e o efeito do cross-currency basis](https://www.cmegroup.com/articles/whitepapers/covered-interest-parity-implied-forward-foreign-exchange-swaps-cross-currency-basis-and-cme-estr-futures.html). **Os dois futuros compartilham o intervalo de referência IMM**, de modo que contratos identificados pelo mesmo trimestre podem estudar mudanças relativas nas taxas overnight. O SR3 corresponde à taxa SOFR (operações com garantia); o ESR, à €STR (operações sem garantia). Alinhamento de prazo **não equivale** a taxas idênticas, taxa básica decidida por BC nem sinal de câmbio à vista. Para precificar forwards, o texto distingue paridade coberta de juros e diferenças de basis.
2. A [CME explica o contrato SR3](https://www.cmegroup.com/education/articles-and-reports/understanding-sofr-futures), com trimestre entre a terceira quarta-feira do mês do código (incluída) e a terceira quarta-feira três meses depois (excluída); ex.: código de setembro/2026 corresponde a **16/09/2026–16/12/2026**. Não se deve rejeitá-lo somente porque a consulta aconteceu em novembro.
3. A [CME descreve o ESR](https://www.cmegroup.com/education/courses/introduction-to-estr/trading-estr-futures), baseado em média composta no trimestre. A [CME também admite liquidação diária baseada em ofertas e spreads](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457088397/ESTR), portanto preço de ajuste **não comprova negociação individual**.
4. [Product Slate da CME](https://www.cmegroup.com/markets/products), com **data de negociação sexta-feira 30/10/2026 e estado PRELIMINARY**, listava para o **produto inteiro**: SR3 **4.735.231 contratos de volume**, open interest **13.040.799**; ESR **185 contratos de volume**, open interest **21.169**. Esses são números **agregados de produto**; não correspondem à liquidez de um vencimento específico, nem a um preço de execução. A página foi pesquisada nesta rodada em **10/11/2026**, sem arquivamento independente dos bytes e sem certificação de hora de divulgação. Não retroceder essa informação em backtests de outubro. A CME diz que boletim preliminar e final podem diferir: [Daily VOI](https://www.cmegroup.com/market-data/volume-open-interest.html).

## Resultado técnico entregue

Arquivo `atlasquant_trader_eurusd_sr3_esr_quarter_lab.py` + `test_atlasquant_trader_eurusd_sr3_esr_quarter_lab.py`, **18 testes sintéticos PASS localmente**, verificam:

- calendário de terceira quarta-feira e virada do ano (ex.: 16/12/2026–17/03/2027);
- pares **USD/SR3** e **EUR/ESR** exigindo mesmo mês-trimestre de referência; não confundem mês de início com mês de vencimento;
- ordem temporal observação → publicação → captura → corte; duas amostras por produto, mesma referência e mesmo dia de negociação entre moedas, sem dados futuros, vencidos ou fonte de hash repetido;
- cotação do tipo `TRADE` exige volume do contrato declarado estritamente positivo; `SETTLEMENT` com volume zero pode ser cálculo de ajuste mas **não atesta execução ou liquidez**;
- preços inválidos e contradições geram abstenção; movimentos de taxa apresentados como **autoafirmações sintéticas**, sem autenticação de dados;
- `AGUARDAR`, sem output de probabilidade, viés operacional, direção spot ou diferencial EUR/USD; sem rede, sem arquivos persistidos ou custos.

**Importante:** campos de hash, horário e volume passados pelo chamador ainda são *alegações*, não prova independente. O `SOURCE_PAGE_RESEARCH_VISIBLE_FROM_UTC` do laboratório é **11/11/2026 00:00 UTC** de forma conservadora e não serve como autenticação de um preço. O produto ESR ter alguma negociação agregada **não garante** liquidez do vencimento em análise. O código não altera o antigo piloto ZQ/FST3, que permanece vetado por divergência de base de períodos.

## Critério para avançar

**Não habilitar sinais no Radar** até obter snapshots licenciados e auditáveis de **mesmo vencimento trimestral**, duas datas de observação, preço/spread/volume por contrato, horário de divulgação, bytes originais hashados e disponibilidade P-I-T; depois medir ganho incremental de contexto de juros em EUR/USD com separação treino/teste, sem assumir causalidade direcional do spot. Se não houver cotações do ESR por vencimento, aguardar ou mudar de fonte em vez de preencher com valores inventados.

**Status final: NO-GO operacional; PR draft; sem merge, deploy, scheduler ou trade.**