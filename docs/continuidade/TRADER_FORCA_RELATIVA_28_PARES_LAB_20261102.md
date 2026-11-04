# AtlasQuant Trader — reconstrução de força relativa FX, somente LAB

Data: 02/11/2026. PR #1803 (DRAFT) · Estado: LAB / HARD NO-GO.

## Objetivo concreto

A análise prioritária é o **viés diário** de cada um dos 28 pares.
O semanal confirma ou contraria esse viés; o mensal fornece contexto
estrutural. A estratégia de entrada com FVG, Order Block e BOS/CHoCH
continua sendo desenvolvida separadamente no TradingView.

Esta etapa evita construir outro universo de Forex: reutiliza o registro
canônico de oito moedas, os 28 pares e a orientação base/cotada do
atlasquant_fx_universe.py e do atlasquant_instrument_registry.py.

## Como a fórmula funciona (versão experimental)

O módulo atlasquant_trader_fx_strength_from_quotes_lab.py recebe apenas
**dados sintéticos explícitos** com preço inicial/final e os horários
UTC com offset de cada um dos 28 pares. Por horizonte (D1, W1, MN1):

- Para o par A/B, calcula r(A/B) = ln(preço_final/preço_inicial).
- Em cada moeda, soma os sete retornos com sinal correto (+ quando
  moeda-base; - quando moeda cotada) e divide por oito, que é a solução
  centrada de mínimos quadrados do grafo completo de oito moedas.
- A soma dos oito fatores relativos é zero. Isso mede **força relativa
  reconstruída**, não valorização absoluta contra um padrão externo.
- O resíduo entre os 28 retornos observados e os retornos reconstruídos
  é aferido; se exceder 15 bps (limiar LAB não calibrado), o horizonte
  inteiro é recusado como possivelmente incoerente.
- Os fatores são transformados para uma escala 0–100 de apresentação,
  com escalas **experimentais específicas por horizonte** (D1 200,
  W1 700, MN1 1500 bps). Valores além da escala são recusados,
  não truncados para sugerir falsa precisão.
- Os três snapshots seguem para o motor de viés anterior, preservando
  D1 principal, W1 confirmação, MN1 contexto.

### Regras fail-closed

Faltou qualquer um dos 28 pares, houve par extra/inverso, fonte
diferente, preço inválido/zero/NaN, horário sem fuso, janela
incompatível, timestamps diferentes, observação do futuro,
período declarado incompatível ou resíduo triangular excessivo:
**AGUARDAR / SEM VIÉS VALIDADO**. Nunca preenche com valores da véspera.

Não são admitidos dados reais pela interface desta versão: exige
state=LAB_SYNTHETIC_SPOT e data_kind=SYNTHETIC_FX_SPOT_CLOSES.
Isto é um modelo de pesquisa e NÃO prova que uma fonte live seja
temporalmente consistente ou tenha permissão de uso.

## Limites e próximos portões

- Pontuações, limiar de neutralidade, normalização e resíduo são
  **hipóteses**, não parâmetros calibrados nem probabilidade de ganho.
- Não há consenso macro integrado ou validação de eventos nesta etapa.
  Uma leitura de força não substitui inflação, juros, política monetária,
  eventos, risco global ou geopolitica.
- Para afirmar qualquer assertividade: adquirir histórico autorizado
  ponto-no-tempo, definir exatamente horários de formação do viés,
  provar ausência de vazamento, medir retorno direcional após cada
  previsão em D1/W1/MN1, baseline neutro/ingênuo, spread/slippage,
  OOS/walk-forward e desempenhos por par e regime.
- **O Top 10 ainda é observacional**, não é recomendação de entrada.

test_atlasquant_trader_fx_strength_from_quotes_lab.py contém 20 testes
sintéticos, incluídos no Quality CI: cobertura 28/8, orientação USD/JPY
e EUR/USD, diversidade de horizontes, falta de dados, timestamps,
fontes e triangulação incoerentes, valores não finitos e travas de operação.

**Sem** merge/deploy, API, consulta EODHD, cron, Worker, conta paga,
paper automático ou ordens. O aplicativo publicado permanece preservado.
