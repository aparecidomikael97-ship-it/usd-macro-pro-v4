# AtlasQuant Trader — PPI de outubro/2026: protocolo de estudo congelado antes do evento (LAB)

## Decisão pré-evento — 11 de novembro de 2026

Esta revisão da PR #1851 documenta um estudo de **um evento econômico** e **sete pares Forex**, antes do PPI dos EUA previsto para 13/11/2026 às 13h30 UTC (09h30 em MT).

O AtlasQuant **não dispõe de um modelo de previsão direcional de PPI prospectivamente validado**. Portanto a decisão de pesquisa deste evento é **ABSTAIN / AGUARDAR**, não compra nem venda. Mesmo que os preços depois subam ou caiam, não poderão ser declarados *acertos* de uma previsão que não foi registrada. O objetivo prospectivo aqui é observar, não avaliar uma taxa de acerto.

O protocolo está codificado em `atlasquant_trader_ppi_pre_event_protocol_lab.py`, com o SHA-256 canônico fixado:

`7905ca757f2a5c3faacb1de06b3e48a24c3115baf07bea5ebe55373ad6fb411f`

Esse resumo documental inclui:
- Evento raiz `US_PPI_OCT2026`, período outubro de 2026 e divulgação programada;
- Os 7 pares USD canônicos: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF e USDCAD;
- Uma vela-base M15 anterior à divulgação e três janelas de reação **+15, +60 e +240 minutos**;
- Consensos pré-evento extraídos dos snapshots TD Economics e Trading Economics arquivados: **+0,4% para PPI final demand** e **+0,3% para PPI sem alimentos e energia**, sempre mês contra mês, com ajuste sazonal;
- Hash dos dois arquivos locais da fonte, e distinção entre consenso da Trading Economics e previsão proprietária da plataforma;
- Direção de estudo `ABSTAIN`, razão `NO_VALIDATED_PRE_EVENT_PPI_DIRECTIONAL_MODEL`, ausência de estimativa do sistema, sem probabilidade calibrada;
- A regra de **uma única amostra econômica**, ainda que observados sete pares correlacionados.

## Relação com os estudos existentes

O novo verificador `inspect_ppi_frozen_research_protocol_lab` confere o código contra um SHA literal, a coorte de sete pares, as janelas, os dois hashes de fontes e o evento. O `atlasquant_trader_ppi_one_event_study_join_lab.py` o chama **antes** de comparar os resultados oficiais e as séries M15.

Se alguém alterar depois da notícia a direção registrada, o consenso, a contagem de pares ou as janelas, a auditoria retorna `PRE_EVENT_RESEARCH_ABSTENTION_PROTOCOL_NOT_INTACT` e não produz o estudo consolidado.

Mesmo após um relatório documental concluído, suas saídas mantêm:
- `pre_event_directional_forecasts_registered=0`;
- `post_event_price_reactions_count_as_predictive_hits=false`;
- `independent_directional_trials_verified=0`;
- `validated_accuracy=null` e `calibrated_probability=null`;
- `operational_bias=AGUARDAR`, sem publicação, alerta ou operação.

## Qualidade de evidência e limitações

O hash fixado é uma **impressão digital dos campos do protocolo**, não uma assinatura digital, um servidor de tempo ou prova de que os dados de origem existiam antes do evento. O histórico da PR no GitHub é a referência externa para **verificar a cronologia de inclusão do código**; a função não faz isso automaticamente nem reivindica auditoria independente.

Os valores de PPI que serão publicados em 13/11 **não estão incluídos**. O primeiro comunicado BLS ainda precisará ser conferido depois de divulgado. As medições de reação exigirão os 17 candles M15 por par, dos quais o último só fechará às **17h30 UTC**, e seguem sem preço bid/ask executável ou fonte autenticada.

Os testes `test_atlasquant_trader_ppi_pre_event_protocol_lab.py` e as regressões do relatório consolidado são **sintéticos**, não dados reais. A CI valida contrato de código, não performance econômica nem modelo.

**Estado de implantação:** PR #1851 rascunho/LAB, sem merge, deploy, coleta automática, negociação ou custos adicionais.
