# Trader — primeiro checkpoint prospectivo de juros britânicos antes do MPC de 05/11/2026

**Data do registro de pesquisa:** 03/11/2026, 11:06:11 UTC. A transcrição deste arquivo e seu futuro commit têm função de **evidência de que declaramos a hipótese antes do evento**. Não provam os bytes originais da página nem horário histórico do Banco da Inglaterra.

## Referência realmente publicada

Fonte primária: https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026

A pesquisa MPS publicada em **18/09/2026**, com respostas de **02 a 04/09**, teve **92 participantes**. Para a pergunta 1a, reunião MPC prevista para **05/11/2026**, percentis da taxa Bank Rate esperada **após** a reunião: **p25 3,75%, mediana 3,75%, p75 3,81%**.

A publicação de 18/09 tem **46 dias no dia 03/11**: ultrapassa o corte cauteloso de 30 dias estabelecido no LAB. Portanto, NÃO é considerada uma expectativa de mercado atual, não mede a probabilidade de uma decisão e não dá viés de alta/baixa para GBP/USD.

## Segunda referência de estudo, ainda sem comparação numérica

O Federal Reserve Bank de Nova York publica os resultados da **Survey of Market Expectations de setembro de 2026**, coletada entre 02 e 08/09, com **62 respostas** e projeções modais da faixa da Fed Funds para reuniões seguintes. A publicação dos resultados ocorre depois da reunião de setembro. PDF: https://www.newyorkfed.org/medialibrary/media/markets/survey/2026/sep-2026-sme-results.pdf

Não foi homologada **data/hora precisa de publicação do PDF nem recibo binário histórico**. Assim, o PDF não é artificialmente marcado como previsão pública antes de reuniões anteriores. A forma da taxa é diferente da britânica: **ponto médio da faixa** esperada do FOMC vs **Bank Rate** da Inglaterra. Mesmo um intervalo temporal aproximadamente igual não produz sozinho expectativa cambial ou uma probabilidade.

## Congelamento e avaliação futuros

- Snapshot documental `docs/continuidade/TRADER_BOE_MPC_NOV5_PROSPECTIVE_FREEZE_20261103.json`.
- `atlasquant_trader_boe_mpc_prospective_lab.py`: valida campos exatos, datas, fonte oficial, percentis decimais, status histórico e corte de 30 dias. Antes de **05/11** não aceita qualquer decisão futura.
- No dia ou após a reunião, sem decisão fonte oficial separada, retorna `LAB_BOE_MPC_PASSED_NO_VERIFIED_ACTUAL`. Um valor posterior **fornecido pelo chamador** só produz diferença matemática em LAB e permanece expressamente **não atestado**.
- `test_atlasquant_trader_boe_mpc_prospective_lab.py`: 30 testes anti-lookahead, anti-falsificação, URL oficial, percentis e NO-GO.
- Os campos `fx_bias`, `fx_probability` e `real_actual_rate_pct` continuam nulos; sem validação OOS, sem alegação de 90%, sem ordem.

**Não autorizados:** merge, deploy, Worker, cron, uso de API paga, corretora, ordens, custo novo ou alteração do visual aprovado.
