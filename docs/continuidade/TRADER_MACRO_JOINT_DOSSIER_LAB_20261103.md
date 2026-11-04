# AtlasQuant Trader — dossiê macro conjunto G8 e pré-eventos (LAB, 03/11/2026)

## Propósito operacional
O usuário prioriza **viés antecipatório** diário/semanal/mensal dos 28 pares Forex e índices, a partir de fundamentos macro, micro, notícias e geopolítica — não OB/FVG/BOS. O dossiê permite ver, lado a lado, o que já estava publicado e quais eventos *ainda viriam*, sem confundir fatos com previsões.

Nova entrada pura: atlasquant_trader_macro_joint_dossier_lab.py
Teste: test_atlasquant_trader_macro_joint_dossier_lab.py
Estado: **LAB / HARD NO-GO**, sem UI/worker/cron/ordem/deploy/merge/custo.

## Fontes reutilizadas (documentais, não feeds)
1. **Inflação G8**: oito leituras oficiais anuais já registradas em atlasquant_trader_g8_inflation_documentary_lab.py: USD 3,7% CPI-U NSA; EUR 3,8% HICP; GBP 3,5% CPI; JPY 2,1%; CHF 1,0% (setembro, até 03/11 UTC) e 1,5% (outubro, elegível 04/11 UTC); CAD 3,1%; AUD 4,3%; NZD 3,7% CPI *trimestral*. Cada observação traz período, publicação, fonte e guarda conservadora.
2. **Decisões de juros G8**: atlasquant_trader_g8_policy_documentary_lab.py, com instrumento específico (faixa Fed, depósito BCE, diretriz aproximada BoJ etc.). A alta RBA de 03/11 é tratada separadamente do início de vigência local em 04/11; decisão BoE prevista para 05/11 exige revisão de seu valor anterior.
3. **Calendário pré-evento parcial**: atlasquant_trader_macro_event_exposure_lab.py. Reunião BoE **05/11** ([BoE](https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates)), emprego EUA **06/11** ([BLS](https://www.bls.gov/schedule/news_release/empsit.htm)) e CPI EUA **10/11** ([BLS](https://www.bls.gov/schedule/news_release/cpi.htm)). As janelas D1/W1/MN1 são rolantes (24h/7d/30d); não são fechamento de velas nem confirmação de reação de mercado.
4. **Pesquisa de expectativa de decisão**: atlasquant_trader_policy_survey_asof_lab.py aceita livro documental opcional validado na estrutura; exemplo congelado em docs/continuidade/TRADER_POLICY_SURVEY_DOCUMENTARY_CASE_20261103.json. Em 03/11, BoE tem pesquisa de setembro **antiga** para evento de novembro; BCE é **agenda, não resultado publicado**; NY Fed sem resultado de pesquisa de outubro observado. As outras cinco moedas não estão cobertas pelo exemplo. Nenhuma expectativa de mercado precificada e com custódia independente está homologada.

## Exemplo contratual — 03/11/2026, 12h UTC
- **GBP/USD, W1**: associação documental CPI e política das duas economias + risco de **MPC BoE 05/11 e NFP 06/11**. CPI EUA de 10/11 fica **fora** da janela dos próximos sete dias se consultado em 03/11 às 12h UTC, mas aparece em MN1. Sem hora inventada para MPC.
- **GBP/USD, D1**: nenhum dos três eventos de catálogo parcial dentro de 24h; isso **não quer dizer** que não haja outros eventos ou notícias.
- **CHF/JPY, W1**: nenhum evento **diretamente associado às moedas do par** nesse pequeno catálogo, não significa ausência de risco global.
- **SPX500, NAS100, US30**: exposição de calendário diretamente associada ao contexto macro USD; ainda faltam micro e geopolítica.
- **WIN/WDO**: eventual evento USD é efeito **indireto não homologado**; faltam especialmente macro do Brasil, política do BCB, riscos fiscais e fluxo local. O dólar não substitui a economia doméstica.

## Guardas de integridade
- Não calcula força da moeda por CPI nem juros nominais entre países com instrumentos/metodologias distintos; diferença, probabilidade e viés ficam **nulos/AGUARDAR**.
- Uma pesquisa documental fora do prazo é etiquetada **PRE_EVENT_BUT_STALE**. Agenda divulgada não é consenso, e dado divulgado após evento não pode voltar no tempo.
- Os dados históricos são transcrições revisáveis, sem arquivos originais autenticados. Fontes incompletas, expectativas de juros e atividade/emprego/geopolítica insuficientes bloqueiam qualquer juízo direcional.
- Cortes conservadores no tempo impedem vazamento de **CHF outubro** antes de 04/11, **RBA novembro** antes do anúncio e **BoE novembro** após chegar a data da nova decisão sem nova checagem.
- Dossiê com 8 moedas, 84 linhas Forex (28 x 3 horizontes) e 15 linhas de índices (5 x 3 horizontes).
- Pesquisa opcional fornecida por chamador é **apenas estruturalmente auditada**; um livro com números falsos poderia passar na forma. Por isso o dossiê **nunca** a converte em probabilidade, força cambial ou previsão verificada.

## Caminho até o viés antecipatório verificável
1. Adquirir capturas ponto-no-tempo/licenciadas e fontes primárias com data/hora e hashes auditados; versão pré-evento do consenso e trajetória implícita de juros por moeda.
2. Ampliar matriz de emprego, atividade, micro e geopolítica — e para WIN/WDO, dados do **Brasil**, não somente EUA.
3. Declarar hipóteses D1/W1/MN1 **antes** da notícia, com tese, cenários condicionais, contraditórios, janela de invalidação e possibilidade de abster-se.
4. Backtest *walk-forward* em preços de fonte **independente** e bases ajustadas por divulgação; avaliar cobertura, precisão direcional, baseline, custos, drift e calibração OOS. **Nenhuma meta de 90% foi comprovada**.

**Governança:** PR DRAFT, no branch de LAB, UI aprovada preservada; sem produção, worker, cron, sinais, corretoras, custos ou merge.
