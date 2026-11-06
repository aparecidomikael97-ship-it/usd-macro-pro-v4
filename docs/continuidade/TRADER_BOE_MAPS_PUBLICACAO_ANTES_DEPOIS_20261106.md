# AtlasQuant Trader — MaPS do Banco da Inglaterra: antes/depois da decisão 05/11/2026

**Estudo documental retrospectivo, 06/11/2026; sem prova histórica independente de captura e sem viés GBP.**

## Fontes e valores transcritos das páginas oficiais

- [BoE MaPS setembro de 2026](https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026): publicado **18/09/2026**; respostas 02–04/09. Para o MPC de 05/11, a **mediana das respostas modais** foi **Bank Rate 3,75%** (92 respostas). Na pergunta **diferente** de probabilidades, 90 respondentes atribuíram em média **35,0%** ao resultado 4,00%. São expectativas antigas, não cotação recente de OIS.
- [BoE MaPS novembro de 2026](https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-november-2026): publicado **06/11/2026**, embora as respostas tenham sido recebidas **21–23/10**. Para o MPC de 05/11, a mediana das respostas modais foi **4,00%** (80 respostas); na pergunta de probabilidades, 78 atribuíram em média **86,0%** ao resultado 4,00%. **Respostas recebidas em outubro não significam resultados agregados públicos em outubro.**
- [Decisão oficial BoE](https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026): publicada **05/11/2026**, elevou a taxa de **3,75% para 4,00%**. O horário exato de publicação não foi atestado; data sem hora só é considerada cronologicamente anterior a partir do início do dia UTC seguinte, por regra de cautela LAB.
- [Política de publicação MaPS do BoE](https://www.bankofengland.co.uk/markets/market-intelligence): resultados agregados são divulgados na sexta-feira após a publicação das atas do MPC. Esta regra explica por que **a rodada de novembro não prova consenso público antes do próprio MPC**.

O snapshot manual `TRADER_BOE_MAPS_NOV5_PUBLIC_VINTAGES_LAB_20261106.json` guarda os valores, datas e fontes para verificação offline. Não contém HTML original nem seu SHA, nem relógio de captura independente. O verificador `atlasquant_trader_boe_maps_nov5_pit_lab.py` bloqueia alterações de resultado, fonte, data ou publicação para essa versão do caso.

## Controle estrito de disponibilidade

| Corte do estudo, em UTC | Contexto que o verificador permite considerar cronologicamente possível |
|---|---|
| Até 18/09 23h59 | Nenhuma das duas pesquisas agregadas |
| 19/09 até a decisão de 05/11 | Pesquisa de setembro (3,75%), sem comprovação de captura histórica |
| A partir de 06/11 00h | Decisão BoE 4,00%, apenas como fato pós-publicação |
| A partir de 07/11 00h | Pesquisa de novembro 4,00%, **somente como documento retrospectivo** |

Esses horários à meia-noite UTC são **cortes conservadores aplicados pelo LAB a páginas com data, mas sem hora de publicação autenticada**. Não afirmam que os documentos foram realmente disponibilizados à meia-noite, nem que foram coletados pelo sistema antes da negociação. O *as-of* do verificador é simulado.

**Diferença simples:** 4,00% realizado menos 3,75% da pesquisa de setembro = **25 pontos-base**. **Não é surpresa monetária contemporânea.** A pesquisa de setembro tinha **48 dias** na data da decisão; a regra experimental de frescor de **30 dias** reprova seu uso como expectativa atual. A pesquisa nova saiu **após** a decisão. Mesmo duas fontes oficiais, não há consenso contemporâneo historicamente observado.

Uma probabilidade subjetiva média de 35,0% ou 86,0% atribuída a uma decisão de taxa não é probabilidade de acerto de trade, nem de valorização da GBP. A primeira pergunta reporta mediana de modas; a segunda, médias de probabilidades, com amostras distintas.

## Próximo passo do motor

Precisamos encontrar e conservar uma medida de expectativa **efetivamente publicada antes da decisão**, com carimbo independente, licença adequada e alvo/instrumento comparáveis. Só então comparar esperado versus realizado; depois avaliar a reprecificação relativa das moedas e comportamento FX com dados de mercado independentes e walk-forward OOS. Não atribuir automaticamente alta da GBP a qualquer aumento de juros.

**LAB/HARD NO-GO:** `market_surprise_bps=null`, `gbp_bias=null`, `fx_bias=null`, `validated_accuracy=null`, `trade_authorized=false`. Sem merge, deploy, Worker, cron, custos, API paga ou mudança de UI. A coorte 56 vagas permanece sem previsões.
