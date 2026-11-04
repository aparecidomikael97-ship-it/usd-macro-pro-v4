# AtlasQuant Trader — Viés e exposições do calendário (LAB, 04/11/2026)

## Decisão do proprietário

Prioridade: macroeconomia, microeconomia, geopolítica, notícias, calendário
econômico, força relativa das oito moedas G8, 28 pares Forex e viés separado
de dia (D1), semana (W1) e mês (MN1). FVG, OB e gatilhos técnicos não são
prioridade desta etapa. Nenhuma nova assinatura, deploy, Worker ou ordem.

## Entrega isolada nesta revisão

- `atlasquant_trader_bias_calendar_exposure_link_lab.py`: combina, **somente
  como explicação sintética**, a matriz de hipóteses de força relativa × macro
  com o calendário **documental parcial** já existente, respeitando os 28
  pares × três horizontes.
- Eventos reportados por moeda-base/cotada, com risco de agenda e precisão do
  horário. Ausência de evento nesse piloto **não** significa ausência de risco.
- A matriz de viés D1/W1/MN1 e as janelas de exposição do calendário de
  24h/7d/30d são conceitos diferentes; o relatório separa explicitamente os dois.
- Proíbe promover qualquer hipótese para viés operacional: todo par/horizonte
  mantém `operational_bias=AGUARDAR`, `trade_authorized=false`, sem preço live,
  probabilidade de acerto, consenso/real validado, integração ao Radar ou
  publicação.
- Confere a reprodução exata do calendário canônico: rejeita omissões,
  adições, datas alteradas, alegação de agenda completa e falsas certificações.
  Também bloqueia relatório de viés sem 28 pares, duplicado, com horizonte
  ausente, direção operacional ou timestamp inconsistente.

## Limitações explícitas

O calendário existente contém **três eventos manualmente registrados**: uma
referência ao comitê do BoE em 05/11, uma ao emprego dos EUA em 06/11 e uma ao
IPC dos EUA em 10/11. Os horários/URLs foram transcritos previamente para
pesquisa e **não possuem custódia de fonte original atestada**. Não há coleta
automática, calendário universal, revisão independente de notícia ou consenso
confiável. A força e o macro usados nos testes são **sintéticos**.

O status `CURATED_EVENTS_IN_WINDOW` apenas sinaliza exposição possível. Não
mede impacto, direção, probabilidade, spread, preço executável nem entrada M15.
Uma data sem hora do BoE pode já ter ocorrido durante o dia — o código
preserva essa incerteza, em vez de inventar uma hora.

## Validação local

```sh
python -m unittest -q \
  test_atlasquant_trader_bias_calendar_exposure_link_lab.py \
  test_atlasquant_trader_bias_priority_bridge_lab.py \
  test_atlasquant_trader_macro_pit_documentation_link_lab.py \
  test_atlasquant_trader_g8_country_macro_catalog_lab.py
```

Resultado em 04/11/2026: **56 testes, OK**, ambiente local. Não é homologação
de fontes reais, não substitui os checks de CI da revisão remota.

## Governança e sequência

Manter PR #1803 em DRAFT/GO-LAB, publicação e núcleo AION em HARD NO-GO.
Próxima validação: ingestão histórica das fontes oficiais por ponto-no-tempo,
confiabilidade independente da agenda e expectativas, relação causal por moeda
e medição OOS de viés D1/W1/MN1 sem reivindicar acerto de 90%.
