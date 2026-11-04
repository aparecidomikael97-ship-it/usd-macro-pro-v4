# AtlasQuant Trader — ponte de viés para avaliação histórica (LAB)

Data: 02/11/2026 · PR #1803 · HARD NO-GO.

## Objetivo aprovado
Priorizar o viés diário dos **28 pares de Forex**. O semanal confirma ou
contraria o diário, e o mensal mostra contexto. FVG, OB, BOS e CHoCH continuam
no script do TradingView, sem criar outro motor de execução.

## Entrega de pesquisa
- atlasquant_trader_bias_forecast_bridge_lab.py liga a reconstrução sintética
  de força do G8 ao motor multihorizonte e ao avaliador OOS já existentes.
- O emissor só recebe preços históricos sintéticos disponíveis até o horário
  da leitura; **não recebe os preços posteriores** usados para conferir
  o acerto direcional.
- Cada lote apresenta exatamente 84 registros (28 pares x D1/W1/MN1):
  ID reproduzível, ativo, horizonte, direção/AGUARDAR, método, hora da decisão,
  hora-limite das informações usadas e motivo de eventual bloqueio.
- O viés diário observacional exige também confirmação semanal. O viés
  semanal e o mensal permanecem descritos independentemente para medir a
  utilidade de cada horizonte; o mensal não substitui o diário.
- O avaliador posterior exige lotes cronológicos, chaves únicas, horários de
  decisão distintos e todos os pares/horizontes presentes. Rejeita duplicações,
  amostras adulteradas estruturalmente, resultados futuros e observações
  incompletas (não permite selecionar apenas os exemplos favoráveis).
- OOS continua com corte fixo treino/teste, expurgo dos resultados de treino
  que cruzam o corte, métricas por par/horizonte, cobertura, abstenções e
  comparação com referência sempre-alta.
- Os testes test_atlasquant_trader_bias_forecast_bridge_lab.py são artificiais:
  validam contratos e recusas, **não medem assertividade do mercado**.

## Limitação essencial
Tudo continua em LAB_SYNTHETIC*. A função não faz I/O ou chamadas de API,
e o lote em memória **não possui custódia imutável**. Um chamador pode
fornecer resultados sintéticos arbitrários; o módulo não os autentica.
Tanto a geração de previsões quanto a avaliação conservam flags
oos_real_proven=False e historical_prices_verified=False.

## Próxima etapa real
1. Escolher fonte histórica autorizada, checar custo/direitos e qualidade
   dos 28 pares com horas point-in-time.
2. Registrar predições antes de conhecer resultados com custódia auditável;
   definir janelas de formação e liquidação, frequência e versão do método.
3. Medir OOS/walk-forward com dados observados e baselines adequados,
   verificando taxa de acerto por par, horizonte, cobertura, regimes e
   incerteza estatística sem prometer resultados.

**Sem** merge, deploy, Worker, cron, API paga, ordens ou qualquer
novo custo. A versão pública e o Checkpoint Mestre seguem preservados.
