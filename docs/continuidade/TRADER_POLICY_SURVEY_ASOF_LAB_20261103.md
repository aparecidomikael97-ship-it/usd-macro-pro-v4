# AtlasQuant Trader — auditoria de expectativas de juros com corte documental (LAB, 03/11/2026)

**Diretriz:** priorizar a antecipação do *viés macro relativo* para 8 moedas/28 pares e índices, por D1/W1/MN1. Esta etapa NÃO estima direção, não mede 90% de acerto e não altera o visual.

## Resultados documentais oficiais (consulta de pesquisa)

1. **GBP / Banco da Inglaterra:** publicação oficial datada de **18/09/2026**: participantes responderam **02–04/09/2026** (92 respostas). Questão 1a, expectativa *modal* mais provável para Bank Rate **após a reunião de 05/11/2026**: percentis p25=3,75%, mediana=3,75%, p75=3,81%. Importante: isso é a **mediana das respostas de política futura**, não probabilidade de corte, preço do GBP ou previsão da decisão do BoE.
   Fonte: https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026
2. **EUR / BCE:** o cronograma **provisório** de 2026 informa reunião de **29/10/2026** e publicação **prevista** do agregado SMA para **30/10/2026**. O cronograma NÃO comprova publicação efetiva nem os resultados numéricos. Mesmo se confirmado, seria depois da reunião citada; inadequado reclassificá-lo como previsão ex-ante da decisão de 29/10.
   Fonte: https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/all-releases.en.html
3. **USD / Federal Reserve de Nova York:** a página oficial em consulta de **03/11/2026** listava perguntas da edição **outubro de 2026**, sem resultado/dados públicos para essa edição. Ela explica que os resultados saem normalmente cerca de três semanas **após** o FOMC. Não inferir medianas não divulgadas.
   Fonte: https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations

### Método de auditoria

- `atlasquant_trader_policy_survey_asof_lab.py` recebe um livro fechado, validando nomes, estados, fontes oficiais, datas ISO, percentis, ordenação e identidade.
- `docs/continuidade/TRADER_POLICY_SURVEY_DOCUMENTARY_CASE_20261103.json` contém a transcrição **manual** desses três registros, com estados distintos: resultado efetivamente publicado, apenas cronograma, resultado não observado.
- Publicação com **data apenas** (sem hora): considere segura **somente a partir de 00:00 UTC do dia seguinte**. Isso é conservador, não prova que o conteúdo estava arquivado na data.
- Proibição integral de usar uma publicação feita no **mesmo dia ou após o evento-alvo**, ou de avaliar a própria decisão no dia de anúncio. Os campos de números são suprimidos nesses casos.
- Limite de **30 dias** para frescor: critério cauteloso de triagem de pesquisa (não calibração financeira nem prazo ótimo estatístico). Em **03/11**, a pesquisa BoE de 18/09 tinha **46 dias**: `PRE_EVENT_BUT_STALE`, não apta a orientar viés novo. A expectativa ainda fica visível como informação histórica identificada.
- Fonte com cronograma é `TIMETABLE_ONLY_NOT_ATTESTED`; sem resultado observado é `RESULT_NOT_PUBLICLY_OBSERVED`. Nunca viram medianas por dedução.
- Datas de publicação retiradas do site são **declarações documentais**; não se possui recibo externo independente, hash histórico assinado ou arquivo web anterior à data. Não confundir isso com evidência ponto-no-tempo plenamente verificada.
- `test_atlasquant_trader_policy_survey_asof_lab.py` cobre vazamento retrospectivo, pesquisas futuras, frescor, URL oficial, percentis, datas erradas, falsificações, segurança e recusa operacional.

### Interpretação para Trader

Uma expectativa de juros da libra **não** permite dizer GBP/USD ALTA ou BAIXA. Precisamos do cenário do Fed, dos diferenciais esperados para horizontes compatíveis, da **surpresa em relação ao que estava precificado**, dos indicadores, micro e geopolítica, com relógio e origem conferíveis. Mesmo com tudo isso, “probabilidade 90%” exige teste real fora da amostra. A saída deste módulo mantém `cross_currency_policy_bias=null` e `policy_probability=null`.

**HARD NO-GO:** sem API paga, corretora, ordem, merge, deploy, Worker, cron, Radar ao vivo, mudança de interface ou cobrança.
