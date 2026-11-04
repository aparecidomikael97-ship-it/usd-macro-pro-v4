# AtlasQuant Trader — Viés multihorizonte FX (LAB, 02/11/2026)

**Decisão do proprietário:** viés diário é a prioridade, semanal é a confirmação,
mensal é contexto. O script ICT/SMC (FVG/Order Block/BOS/CHoCH) permanece
separado no TradingView. O AtlasQuant deve explicar qual das oito moedas está
mais forte e o viés direcional de cada um dos 28 pares, com incerteza explícita.

## Reaproveitamento do Checkpoint Mestre

- atlasquant_fx_universe.py e atlasquant_instrument_registry.py
  são fonte canônica das oito moedas, 28 pares, orientação base/cotada,
  diferencial de força e intensidade de ranking **não probabilística**.
- A macro orienta a direção; ICT/SMC determina localização/timing.
  Viés **não é** gatilho nem autorização de execução.
- Sem evidências, com conflito, horário ausente, período inválido
  ou valor não finito: **AGUARDAR**, nunca inventar um lado.
- O Checkpoint Mestre original (22/09) e a reconciliação (29/09)
  continuam válidos; esta decisão de 02/11 detalha a prioridade Trader.

## Entrega técnica isolada

- atlasquant_trader_bias_horizons_lab.py: modelo puro, **sem rede/armazenamento**,
  alimentado apenas com snapshots LAB_SYNTHETIC para D1/W1/MN1.
- 28 linhas e Top 10 **somente observacional**, filtrado por alinhamento diário
  e semanal, não por chance de lucro. Mensal contrário aparece como aviso.
- Cada horizonte exige origem, método de cálculo, período, horário com fuso,
  oito pontuações 0–100 e frescor adequado. Métodos heterogêneos não se
  misturam. O dado é explicitamente **índice de força**, não valorização nominal.
- 17 testes de simulação cobrem faltas, conflitos, dados futuros/velhos,
  orientação do par, NaN/booleanos, métodos diferentes, neutro, limites
  e nenhum gatilho de execução.
- Limiar experimental de 5 pontos é parâmetro de LAB, **não calibrado**.
  Índice e ranking **não representam** probabilidade de acerto.

## Portões não concluídos

- Escolha auditável da metodologia de força por horizonte, com mesmas fontes
  de 28 pares e horários consistentes; documentação de unidades/cobertura.
- Fusão **não arbitrária** com fundamentos macro e eventos do Painel Mestre.
- Histórico de preços sem vazamento do futuro, custos/fricção, baselines,
  backtests OOS e walk-forward por par/horizonte; métricas por regime.
- Só depois revisão independente e eventual integração ao Radar; nenhuma
  publicação, sinal ou execução real está aprovada.

**HARD NO-GO:** sem merge, deploy, Worker AION, APIs, cron, conta paga
ou ordens reais. Nenhuma afirmação de assertividade ou de cobertura real.
