# AtlasQuant Trader — Horário de avaliação e congelamento de evidências D1 (LAB)

Data: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO

## Decisão que estamos protegendo

O usuário priorizou a **assertividade do viés dos 28 pares**.
D1 é a direção mais importante, W1 é a confirmação e MN1 é contexto.
O script ICT/SMC (OB, FVG, BOS/CHoCH) permanece separado no TradingView.
A atualização do **calendário às 00h** (requisito de produto) NÃO significa
que dados publicados ao longo do dia já eram conhecidos naquela hora.

Para medir um viés histórico com justiça, a hora de observação tem de ser
escolhida ANTES dos resultados. Podemos atualizar a interface com dados novos
durante a sessão sem tratar cada atualização como mais uma previsão
independente e sem reescrever a observação congelada da manhã.

## Entrega de pesquisa isolada

- Arquivo: atlasquant_trader_bias_daily_freeze_lab.py
- Testes: test_atlasquant_trader_bias_daily_freeze_lab.py
- O horário **07:00 America/Cuiaba**, segunda a sexta, é somente
  **CANDIDATO DE LAB** para criar uma amostra reproduzível. Não é
  aprovado como preferência do proprietário, nem ativa cron ou Worker.
- Aceita apenas lotes LAB_SYNTHETIC_ISSUED do motor existente, com
  **84 registros exatos (28 pares x D1/W1/MN1)**, IDs canônicos,
  método único e horário da decisão idêntico para todo o lote.
- Exige uma origem sintética da força relativa G8 identificada com
  cobertura exata das oito moedas; não valida sua fórmula nem confunde
  a referência BCE com cotação Forex negociável.
- Cada evidência declara ID, origem, momento a que se refere e
  instante de captura. Uma evidência capturada **depois da decisão**
  recusa o congelamento inteiro.
- Um resultado macro ("MACRO_ACTUAL_RELEASED") só pode constar
  quando foi divulgado e recebido antes do corte da previsão.
  Um evento FUTURO pode constar como "MACRO_SCHEDULE_ONLY", mas
  não pode conter o resultado nem surpresa econômica.
- Uma assinatura SHA-256 do JSON é criada apenas como identificador
  reproduzível de conteúdo: **não é prova de custódia, assinatura
  independente ou de captura realmente realizada naquela hora**.
- A data UTC do dia de pesquisa e os dias de semana são convenções
  de LAB; datas de sessões Forex e feriados ainda exigem auditoria.
- Não existe nesta entrega qualquer ingestão de dados de mercado,
  histórico real, API, saldo, operação, publicação ou agenda ativa.

## Critérios que continuam bloqueando assertividade

O congelamento de exemplo é **LAB_FROZEN_SYNTHETIC_OBSERVATION**.
O protocolo retorna, sem exceções, real_market_sources_verified=False,
real_historical_capture_verified=False, real_oos_accuracy_proven=False,
can_feed_live_bias=False, can_feed_real_backtest=False,
trade_authorized=False e scheduler_enabled=False.

Para provar assertividade de viés no mundo real será preciso:
1. Coletar dados de fornecedor cujo custo/uso esteja autorizado,
   com horários de publicação e efetiva disponibilidade atestados.
2. Registrar previsões imutáveis ANTES do evento previsto, com
   origem e versão da lógica, sem permitir revisões retrospectivas.
3. Testar resultados posteriores, por par/horizonte, em OOS e
   walk-forward, com cobertura, resultados neutros, baselines e
   dependência temporal entre previsões.
4. Medir o ganho efetivo dos fundamentos macro sobre o baseline
   apenas com indicadores conhecidos na hora da decisão.
5. Submeter metodologia, horário escolhido e resultados à revisão
   independente, antes de expor estatísticas como confiáveis.

**HARD NO-GO:** sem merge, deploy, Worker, agendamento, novas
contratações, consumo de API ou ordens. Interface publicada preservada.


## Revisão: compromisso do plano macro na observação original

Um veto macro datado separadamente do viés poderia ser inventado
depois de conhecer o resultado do preço. Para reduzir esse risco
de consistência interna, freeze_daily_bias_observation_lab agora
aceita macro_vetoes=[] (ou lista explícita):

- O método de pesquisa é fixo:
  MANUAL_PREDECLARED_MACRO_VETO_D1_LAB_V1.
- Cada veto D1 só altera ALTA/BAIXA para AGUARDAR no comparador.
  Precisa referenciar um evento MACRO_ACTUAL_RELEASED da moeda
  base ou cotada já divulgado e capturado antes do horário de emissão.
- IDs, decisão, justificativa, método e evidências macro entram
  junto com o lote dos 84 vieses no MESMO SHA-256 de conteúdo.
- Modificar a justificativa, fonte, evento, ID ou a presença de
  um veto altera o hash da observação. Eventos futuros
  MACRO_SCHEDULE_ONLY não podem justificar veto.
- Uma observação sem veto também registra essa escolha
  (plano vazio) no conteúdo congelado.
- O comparador LAB exige que o hash registrado anteriormente
  pelo próprio experimento coincida com o recalculado.
  Divergência significa recusa, sem seleção posterior.

**Limite crítico:** hash SHA-256 gerado com dados enviados pelo
chamador NÃO prova que a previsão existia historicamente, pois
o usuário pode alterar tanto o plano quanto o hash. Falta
carimbo confiável de tempo, testemunha independente e
armazenamento imutável para prova real. Não declarar
assertividade real por passar os testes.
