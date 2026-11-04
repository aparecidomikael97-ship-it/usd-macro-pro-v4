# AtlasQuant Trader — fontes públicas de EXPECTATIVAS de juros G8 (LAB, 03/11/2026)

## O resultado real desta pesquisa

Encontradas páginas oficiais contendo **pesquisas de expectativas de política** para cinco das oito moedas (USD, EUR, GBP, CAD, NZD), **uma publicação de contexto/precificação** para AUD, e **duas lacunas** (JPY, CHF) na categoria específica de pesquisa pública de trajetória futura comparável. Não confundir as lacunas com inexistência de instrumentos de mercado: significa apenas que **não homologamos aqui uma série oficial pública correspondente**.

Uma pesquisa publicada em uma página de banco central **não é** taxa de câmbio ao vivo, nem cotação OIS independente com licença, nem probabilidade calibrada de alta/baixa do par.

| Moeda | Fonte pública oficial documentada | Produto e limitação para D1/W1/MN1 |
|---|---|---|
| USD | [NY Fed — Survey of Market Expectations](https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations) | Pesquisa junto a participantes; **resultados são divulgados cerca de três semanas DEPOIS da reunião** pertinente. Em 03/11, a página mostrava perguntas de outubro sem os respectivos resultados; resultados futuros não podem ser retroinjetados como consenso pré-FOMC. |
| EUR | [BCE — Survey of Monetary Analysts](https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/index.en.html) | Expectativas por reuniões de política; a edição de outubro de 2026 foi divulgada após decisão de 29/10. Não usar como se fosse a previsão publicada ANTES daquela decisão. |
| GBP | [BoE — Market Participants Survey, setembro/2026](https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026) | Pesquisa anterior à reunião de 05/11, mas de setembro; inclui distribuição de opinião e 90 respostas para a questão específica. Não é OIS nem previsão FX. |
| CAD | [BoC — Market Participants Survey](https://www.bankofcanada.ca/publications/market-participants-survey/) | Publicação aproximadamente duas semanas após algumas decisões; Q2/2026 confirmado, próxima divulgação oficial programada para 09/11 — **não é dado conhecido em 03/11**. |
| NZD | [RBNZ — Survey of Expectations](https://www.rbnz.govt.nz/hub/home/statistics/series/economic-indicators/survey-of-expectations) | Média de opiniões sobre OCR fim do trimestre e um ano adiante; não estimativa diária de cada reunião. Edição de agosto/2026 como referência documental. |
| AUD | [RBA — Statement on Monetary Policy, novembro/2026](https://www.rba.gov.au/publications/smp/2026/nov/financial-conditions.html) | Comenta trajetória inferida de OIS, mas a exposição não entrega neste laboratório uma curva bruta sincronizada e direitos de redistribuição verificados. |
| JPY | [BoJ — Money Market](https://www.boj.or.jp/en/paym/market/) | A pesquisa pública sobre funcionamento do mercado monetário NÃO é levantamento por reunião sobre a trajetória futura da taxa. Série comparável ainda não encontrada/homologada. |
| CHF | [SNB — Monetary Policy Decisions](https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions) | Decisões e projeção condicional de inflação; projeção que supõe taxa de juros fixa **não é opinião do mercado** sobre juros futuros. |

**Atenção à cronologia:** documentação revisada em 03/11 não contém comprovante independente de horário histórico original de cada publicação. Para evitar datar esta nova compilação antes de existir, o código só permite usá-la como catálogo documental a partir de **04/11/2026 00:00 UTC**. Isso não significa que as pesquisas não estivessem publicadas antes; é apenas a política conservadora deste laboratório.

## Um caso real de expectativas, sem virar sinal Forex

Na pesquisa de setembro do **Bank of England**, questão 1cii, os respondentes deram as probabilidades médias para a taxa Bank Rate **após a reunião de 05/11/2026**:

| Faixa/taxa Bank Rate | Probabilidade média dos entrevistados |
|---|---:|
| Inferior a 3,50% | 0,3% |
| 3,50% | 1,7% |
| 3,75% | 60,4% |
| 4,00% | 35,0% |
| 4,25% | 2,4% |
| Acima de 4,25% | 0,3% |

**As porcentagens totalizam 100,1% por arredondamento publicado a uma casa**; manter os números originais, sem normalização oculta. A pergunta recebeu **90 respostas**. São probabilidades **das opiniões de entrevistados sobre a decisão de juros**, não **probabilidades de GBP/USD subir ou cair**, nem leitura de mercado em 03/11, nem assertividade de trading.

Também é possível encontrar nesta pesquisa o valor mediano modal de **3,75%** para a reunião de novembro, mas uma mediana e as probabilidades médias dos respondentes são estatísticas diferentes. Não reduzir tudo a um único número de direção.

## Contrato de segurança dos dados

- `atlasquant_trader_g8_policy_survey_leads_lab.py`: inventário congelado de oito fontes, mais distribuição pública do BoE separada do sinal FX.
- `test_atlasquant_trader_g8_policy_survey_leads_lab.py`: 31 testes locais de 8 fontes, 28 pares × 3 horizontes, fonte/janela/corte conservador, valores congelados, divulgação pós-reunião, probabilidade de pesquisa ≠ FX, recusa de alterações e HARD NO-GO.
- Todas as **84 linhas de par e horizonte** retornam `directional_bias=AGUARDAR` e `expectation_gap_bp=null`: **ainda não temos oito curvas homogêneas e sincronizadas**.
- Nenhuma fonte é consumida por HTTP no código, nenhum token cadastrado, nenhum dado adquirido com restrição ou custo, nenhuma credencial e nenhuma cotação implementada.

**Próximo degrau:** procurar por moeda dados de expectativas de igual vencimento (OIS/meeting-date surveys), capturar o *momento anterior* da divulgação e verificar termos. Só promover comparação relativa quando os dois lados do par tiverem metodologia, maturidade, horário e licença compatíveis, seguida de backtest independente walk-forward.

**PR #1803 segue DRAFT / LAB / HARD NO-GO.** Interface aprovada, `main`, produção, Worker AION, cron, deploy, ordens e custos permanecem intocados. `accuracy_90_proven=false`, `probability_calibrated=null`.
