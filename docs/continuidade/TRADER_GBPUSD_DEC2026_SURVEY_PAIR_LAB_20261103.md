# AtlasQuant Trader — dois levantamentos oficiais de juros para dez/2026 (LAB 03/11/2026)

Objetivo do proprietário: **viés macro antecipatório** em Forex e índices, não FVG/OB. Esta etapa guarda duas opiniões já publicadas para futuras reuniões, não atribui direcional GBP/USD.

## Fontes e leitura cuidadosa

**GBP — Banco da Inglaterra, Survey of Market Participants, setembro de 2026**

Publicada em **18/09**; pesquisados 02–04/09, **92 respostas**. Pergunta 1a, **Bank Rate após MPC 17/12/2026**, p25=3,75%, mediana=3,75%, p75=4,00%.

https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026

**USD — Fed de Nova York, Survey of Market Expectations, setembro de 2026**

PDF de 16 páginas, distribuído 02/09, fechado em 08/09, **62 respostas**. Pergunta **2a**: mediana da previsão *modal de cada respondente* do **ponto médio da faixa-alvo do Fed após FOMC 08–09/12/2026**: **3,63%**, p25=3,63%, p75=4,13%. A página de pesquisa já disponibiliza os resultados em consulta de 03/11, mas a **data/hora da primeira publicação do PDF não foi atestada**. Não reclassificar dados posteriormente disponibilizados como se estivessem públicos antes da reunião de setembro.

https://www.newyorkfed.org/medialibrary/media/markets/survey/2026/sep-2026-sme-results.pdf

Página que lista resultados disponíveis:
https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations

### Regra de tempo

Registro manual em **03/11/2026**, sem bytes dos documentos ou recibo externo histórico. O `atlasquant_trader_gbpusd_dec_policy_surveys_lab.py` trata a *primeira data em que a pesquisa foi vista neste LAB* como **apta a partir do dia UTC seguinte**, conservadoramente. A data original do BoE é 18/09; a data original exata de divulgação do PDF NYFed **não é inferida**.

Ambas as pesquisas foram respondidas em **setembro**. Em novembro, são dados históricos antigos, não substituem consenso atualizado, expectativas precificadas em futuros ou OIS. Dezembro tem **datas diferentes de reunião**, amostras distintas e formas distintas de expressar a taxa (Bank Rate vs ponto médio da faixa Fed). Mesmo que duas medianas existam, a subtração **não é um diferencial de OIS validado nem uma probabilidade de GBP/USD subir ou cair**.

### Entrega técnica e restrições

- `docs/continuidade/TRADER_GBPUSD_DEC2026_SURVEY_PAIR_FREEZE_20261103.json`: transcrição manual documental dos dois painéis.
- `atlasquant_trader_gbpusd_dec_policy_surveys_lab.py`: valida fonte, valores e tipo de survey, publicação, datas-alvo, recusa retroatividade; exibe apenas medianas como histórico **antes do primeiro evento de dezembro** e após corte UTC conservador.
- `test_atlasquant_trader_gbpusd_dec_policy_surveys_lab.py`: **27 testes** para atestado inexistente, convenções trocadas, números alterados, datas falsas, viés não autorizado.
- Resultado `LAB_STALE_DOCUMENTARY_DEC_POLICY_PAIR_ONLY` antes das reuniões, depois `LAB_DEC_POLICY_PAIR_TARGET_PASSED`. `fx_bias=AGUARDAR`, `fx_probability=null`, nenhum diferencial numérico calculado, nenhuma promessa de 90%.

**HARD NO-GO:** sem compra de dados, merge, Worker, cron, deploy, ordens, radar em produção ou mudança na interface aprovada.
