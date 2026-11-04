# AtlasQuant Trader — prioridade oficial do viés (04/11/2026)

**Decisão explícita de Mikael:** a prioridade é o viés dos 28 pares e a força
das oito moedas, com contexto macro, microeconomia, geopolítica, notícias e
calendário econômico. D1 (principal), W1 (confirmação), MN1 (contexto).
**Não é prioridade:** FVG, Order Block, BOS/CHoCH e replay de entradas.
O PR #1814 permanece pausado, sem apagar a pesquisa anterior.

## Novo contrato explicativo de laboratório

`atlasquant_trader_bias_priority_bridge_lab.py` conecta *somente dois
contratos sintéticos* já existentes no PR #1803:

1. A matriz de força relativa G8/28 pares D1/W1/MN1
   (`atlasquant_trader_bias_horizons_lab.py`).
2. Hipóteses condicionais macro/micro/geopolítica pré-evento
   (`atlasquant_trader_exante_macro_scenarios_lab.py`).

Para cada um dos 28 pares e três horizontes (84 leituras), o relatório mostra:

- hipótese direcional da **força relativa**, reconstruída a partir das oito
  pontuações declaradas (não é valorização cambial observada);
- hipótese macro condicional declarada antes do corte temporal;
- se são *hipóteses concordantes*, *conflitantes*, *neutras* ou *incompletas*;
- evidências ainda não homologadas: macro, micro, geopolítica, notícias,
  calendário econômico e procedência da força relativa;
- **viés operacional `AGUARDAR` em todos os casos**, inclusive quando as
  hipóteses sintéticas concordam.

O relatório confere 28 pares canônicos, 8 moedas, 3 horizontes, ausência de
duplicações, horários de publicação/corte, que a força congelada não use
informação posterior à hipótese macro, consistência da posição mais forte e
mais fraca com as pontuações, e consistência dos 28 pares com as respectivas
moedas-base/cotada. Recusa livros que alegam operação/autenticação real.

## Limites fundamentais

- Testes sintéticos **não** validam modelos de previsão, fontes, tempo real,
  acerto de mercado, consenso econômico ou histórico point-in-time.
- Acordo entre dois modelos sintéticos não prova assertividade: as evidências
  podem ter sido escolhidas manualmente e não são independentes.
- A ausência de notícia ou calendário validado nunca é substituída por uma
  seta de alta/baixa; o contrato responde AGUARDAR.
- `real_sources_attested=false`, `historical_vintage_attested=false`,
  `market_forecast_verified=false`, `probability_calibrated=null`,
  `accuracy_90_proven=false`, `can_feed_live_radar=false`,
  `trade_authorized=false`, `publishable=false`.

## Próximas etapas reais, por prioridade

1. Evidências oficiais macro e contexto micro/geopolítico por moeda, com
   horários, expectativas, histórico e fontes auditáveis.
2. Calendário econômico e notícias: separar anterior, consenso, divulgado,
   surpresa e mudança posterior das expectativas.
3. Integrar dados de força relativa legitimamente obtidos, D1/W1/MN1,
   explicitando se são referências BCE derivadas ou preços independentes.
4. Reunir explicações para cada par e cada horizonte, com conflitos e
   invalidação; só após evidência suficiente considerar validação no Radar.
5. Backtests fora da amostra sem promessa de 90%.

**Governança:** PR #1803 DRAFT/LAB/HARD NO-GO, sem custos, merge, Render,
Worker, ordens, corretoras, AION ou mudanças no visual aprovado.
