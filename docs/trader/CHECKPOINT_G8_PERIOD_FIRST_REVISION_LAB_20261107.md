# AtlasQuant Trader — escolha de período macro G8 na auditoria as-of

**Data:** 07/11/2026. **Estado:** LAB / Draft; não integrado ao Radar nem ao viés operacional.

## Problema encontrado

No módulo `atlasquant_trader_g8_macro_asof_lab.py`, a seleção de CPI/juros
com vários períodos disponíveis dava prioridade ao último `published_at_utc`.
Isso faz um número de **período antigo republicado depois** tomar o lugar da
observação mais recente. Não é uma comparação macro correta: por exemplo,
um CPI de agosto revisto em novembro não substitui o CPI de setembro já publicado
em outubro.

## Correção isolada

- Selecionar primeiro o maior `observation_period` válido e, apenas em empate,
  a publicação mais recente (empates do mesmo período já são bloqueados).
- A validação temporal existente permanece: publicação e captura antes da
  decisão, sem duplicatas do mesmo indicador/período, sem fonte desconhecida.
- Os números de inflação/juros continuam **não expostos** ao cálculo de força;
  o resultado da auditoria segue `CALLER_ASSERTED_NOT_INDEPENDENT`, `AGUARDAR`,
  `can_feed_live_radar=False` e `trade_authorized=False`.
- Teste 1: revisão tardia de agosto não toma lugar de setembro.
- Teste 2: revisão recente de maio não deixa um período de junho vencido
  passar pelo gate como se estivesse atual.

## Limites pendentes

- Essa mudança é um reparo de seleção e **não comprova** origem, horário real,
  série histórica original, revisões de valores nem consenso pré-divulgação.
- A regra de frescor ainda é por `published_at_utc` informado pelo produtor,
  sem auditoria independente e sem regra por calendário/periodicidade de cada
  país; publicar uma revisão isolada não basta para comprovar atualidade do
  indicador. Uma política de vintage/periodicidade verificada continuará
  necessária antes de alimentar as 28 combinações de moedas.
- Não há acerto de viés validado, recomendação, ordem, deploy, custo, Worker
  nem alteração do checkpoint original. Macro W1/D1 segue como prioridade.
