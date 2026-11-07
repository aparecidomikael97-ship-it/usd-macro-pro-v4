# AtlasQuant Trader — Reconciliação do Checkpoint Mestre — 04/11/2026

**Escopo vigente aprovado:** somente AtlasQuant Trader · Forex e Índices, nas três abas **Início, Radar e Painel Mestre**. As áreas AION, Negócios e Investimentos continuam preservadas/congeladas. A ausência da antiga aba Scanner Técnico é intencional; OB/FVG/BOS/zonas continuam no script TradingView, sem obrigação de reproduzir o scanner antigo dentro do Radar.

## Documentos auditados
- `docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md`
- `docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md`
- `docs/trader/CHECKPOINT_VIES_MULTITEMPO_LAB_20261103.md`
- Código em `atlasquant_trader_radar_compact_ui.py`, `atlasquant_trader_bias_matrix.py`, `atlasquant_win_opening_calculator.py`, calendário e testes.

As decisões mais recentes do proprietário substituem prioridades antigas de expansão do AION. **Não alterar nem apagar o histórico do Checkpoint Mestre ou liberar operação real.**

## Plano por aba e estado de execução

| Área | Item | Estado | Observação |
|---|---|---|---|
| Início | Três abas e acesso simplificado | VALIDADO | Já publicado anteriormente |
| Início | Diagnóstico de confiabilidade: 28 pares, bloqueios e o que falta | IMPLEMENTADO / EM VALIDAÇÃO | Nova revisão LAB; sem cotações inventadas |
| Início | Resumo macro + eventos de alto impacto reais | DEPENDÊNCIA EXTERNA | Fonte/autenticidade, frequência e horário por verificar |
| Radar | Matriz W1/D1/H4/M15 dos 28 pares, recolhida | VALIDADO (interface) | Alimentador de mercado ainda não validado |
| Radar | Explicação individual 'Por que não?' | IMPLEMENTADO / EM VALIDAÇÃO | Esta revisão LAB; 28/28 sem autorização de entrada |
| Radar | Força relativa das 8 moedas e Top 10 por valorização diária | DEPENDÊNCIA EXTERNA | Requer fonte completa, atual, verificável e escopo de custo aprovado |
| Radar | Índices Brasil/EUA/Europa/Ásia, WIN/WDO separados | IMPLEMENTADO (apresentação) | Sem atribuir viés real a índice sem dados |
| Radar | Calculadora manual de abertura WIN | VALIDADO (UI/manual) | Publicada na PR #1808; score = minério + petróleo − VIX; limiares não calibrados |
| Radar | Automação do WIN e regra específica do WDO | DEPENDÊNCIA EXTERNA | Não herdar pesos Forex/WIN e não ligar sem provas |
| Painel Mestre | Conteúdo macro, micro, geopolítica, calendário e contexto | IMPLEMENTADO (estrutura) | Explicações condicionais; feed de notícias pendente |
| Painel Mestre | Checklist de evidência, risco e motivo de bloqueio | IMPLEMENTADO / EM VALIDAÇÃO | Esta revisão LAB |
| Painel Mestre | Calendário EODHD | IMPLEMENTADO (pipeline) | Disponibilidade real e cobertura ainda requerem validação |
| Todas | Viés assertivo e taxa de acerto comprovada | APROVADO / PENDENTE | Sem 80% declarados; requer backtest OOS, walk-forward, paper, custo/R líquido |

## Regras da decisão
- Macro orienta; D1/W1 contextualizam; H4 confirma estrutura; M15 verifica alinhamento. OB/FVG/estrutura de preço validam **localização** e **gatilho**. Viés NÃO equivale a entrada.
- Ausência, conflito, prazo vencido ou origem não verificada => **AGUARDAR / NÃO OPERAR**. Não preencher métricas com valores de exemplo.
- Nenhuma leitura do Radar, mesmo alinhada, habilita ordem real. Checagem de risco precisa ser independente.
- O score interno não é probabilidade de lucro. A meta desejada de assertividade >=80% é **aspiração, não resultado medido**; medir também R líquido, custos, slippage, taxa de cobertura, drawdown e estabilidade fora da amostra.
- Preservar interface compacta e responsiva, sem novo Scanner Técnico, sem duplicar tabela Forex, sem gasto adicional, sem AION Worker/deploy.

## Ordem da próxima implementação, sem nova cobrança
1. **Agora:** 'Por que não?' explicável e consistente nas três abas, com testes unitários e browser; sem feeds falsos.
2. **Depois:** inventariar provedores/caches existentes, validar fonte e freshness; dados diários 28/28 e força G8 com metodologia documentada.
3. **Depois:** adicionar macro de maneira separada do preço (surpresa versus consenso, risco de evento, fonte e horário), calendário e notícias relevantes, sem inventar direção causal.
4. **Depois:** backtests out-of-sample e walk-forward por ativo/timeframe/sessão; paper trading antes de recomendar qualquer uso operacional.

## Critério de fechamento
Esta revisão não alega viés real calibrado, probabilidades, 80% de acerto ou integração externa. Validar em CI, conferir acessibilidade e navegação Início/Radar/Painel Mestre, aprovação humana antes de publicar gradualmente. Núcleo AION permanece HARD NO-GO.


## Adendo 07/11/2026 — três camadas de inteligência e validação do viés

**Pedido do proprietário:** aumentar assertividade de viés dos 28 pares sem desviar do produto AtlasQuant Trader, sem novas cobranças, sem ordens e sem promessa de 60%, 80% ou 90%. Preservadas três abas Início, Radar, Painel Mestre; W1/D1 prioritários, H4/M15 auxiliares; AION, Negócios e Investimentos congelados.

### Três camadas alinhadas — mesma prioridade central

1. **Pré-notícia / Nowcast do dado** — EXISTENTE EM LAB / NÃO CALIBRADO: `atlasquant_news_nowcast.py`, `atlasquant_news_backtest.py`. Estimar distribuição ABAIXO/EM LINHA/ACIMA do consenso da publicação específica e valor aproximado antes do evento, com anterior, consenso, antecedentes, registros point-in-time, avaliação walk-forward e baseline de consenso. Nunca interpretar probabilidade de classe como probabilidade de subida do par ou ganho.
2. **Notícia × posição aberta** — EM IMPLEMENTAÇÃO / LAB NÃO VALIDADO: `atlasquant_position_event_manager.py` e proposta `atlasquant_position_news_audit_lab.py` na PR rascunho #1844. Comparar impacto macro hipotético sobre moeda base/cotada e tese LONG/SHORT, sugerindo somente revisão de manutenção/stop/saída conforme evidência e risco, sempre com controle humano; nunca fechar ou manter automaticamente.
3. **NOVO ADENDO: Motor de Regimes + Probabilidades Calibradas + Contexto Institucional** — APROVADO COMO DIRETRIZ DE PESQUISA / PENDENTE DE IMPLEMENTAÇÃO E VALIDAÇÃO. Objetivo: estimar, para cada par e horizonte D1/W1, sob qual regime e conjunto verificável de fatores existe vantagem estatística sobre baselines simples, com abstenção quando não existir. Não prometer acesso à intenção de bancos ou às ordens ocultas.

### Componentes propostos (não declarar implementados)

- **Regime:** classificar TREND, RANGE, TRANSIÇÃO/CHOQUE e VOLATILIDADE ANORMAL a partir de observações disponíveis *antes* da decisão; usar séries de volatilidade, tendência e risco sem olhar candles futuros. Reavaliar eficácia por regime e por D1/W1.
- **Macro relativo e expectativa:** separar NÍVEL de juros/inflação de SURPRESA frente ao consenso, revisões, diferencial de expectativas de política monetária, crescimento/emprego e mudanças de prêmio de risco. Moeda base vs cotada, séries/instrumentos/periodicidades compatíveis e governança de vintages.
- **Institucional / fluxo proxy:** pesquisar CFTC COT/TFF por moeda, categorias (leveraged funds, asset managers, dealers) e mudanças de posicionamento; dado de terça divulgado normalmente sexta e derivado de futuros, NÃO livro completo de ordens do Forex spot. Outros observáveis como curva de juros, spreads, volatilidade implícita e skew de opções somente com fontes/licenças válidas e sob orçamento autorizado; não contratar nesta fase.
- **Intermercados / risco:** observar juros curtos/longos, risco global, commodities relevantes e correlações, testando se fornecem previsão incremental e não contagem duplicada de sinais correlacionados. DXY/pares USD exigem cuidado contra dupla contagem.
- **Ensemble auditável e seletivo:** comparar modelos simples (consenso, prevalência, momentum, macro) com modelos combinados ajustados apenas em treino. Só mostrar direção + intervalo/probabilidade se *calibrados fora da amostra*, senão NEUTRO/AGUARDAR. Score interno, confiança estatística e probabilidade de ganho são campos distintos.
- **Risco e payoff:** acompanhar custo total, spread, slippage, stop, payoff médio em R, expectativa líquida, profit factor, drawdown e concentração/correlação dos sete pares com uma mesma moeda. Acerto direcional >50% não garante lucro; lucro não exige necessariamente >50% de acertos.

### Protocolo obrigatório de prova (antes de qualquer promoção)

0. Primeiro resolver o gargalo atual: fontes oficiais por ambas as moedas, fonte de preços MT5 somente leitura/horários, ponto no tempo independente, consensos originais e política de frescor por competência, não pela data de revisão.
1. Congelar antes da decisão: horizonte D1/W1, horário, dado disponível, regime, previsão ALTA/BAIXA/NEUTRO/AGUARDAR, probabilidades e versões do modelo; registrar timestamp externo verificável.
2. Backtest cronológico com walk-forward, validação fora da amostra e embargo entre janelas sobrepostas; sem escolher hiperparâmetros pelo conjunto de teste. Confrontar baseline simples, apurar Brier/log-loss, calibração, taxa de cobertura, matriz de confusão, taxa de acerto **condicional a sinais emitidos**, falso positivo, estabilidade por par/regime/sessão.
3. Medir reação do preço separadamente da previsão do número da notícia; simular custo/execução e resultado líquido em R, inclusive piores cenários e concentração de posições.
4. Fazer forward/paper por período suficiente, com análise de drift e decisão de revisão humana; se faltar evidência, manter AGUARDAR e não inventar confiança nem métricas.
5. **HARD NO-GO:** nenhuma ordem, alteração de risco real, auto-hold/exit, Worker, merge/deploy ou nova cobrança autorizada por este adendo.

### Ordem real da fila

**P0 — preservar foco:** completar comparabilidade macro bilateral G8/28 e histórico de fontes, preços e vintages; revisar as três consultas diárias (consultar ≠ indicador novo).
**P1 — provar o básico:** definir rótulos de movimento D1/W1, baselines e auditoria walk-forward/pre-registro.
**P2 — experimentos baratos em paralelo no LAB:** regime a partir de OHLC existente, curva/juros públicos, COT/TFF público semanal (já constava do roadmap como fase futura, não declarar novidade concluída), testes de valor incremental.
**P3 — depois da prova:** ensemble e probabilidade calibrada/abstenção; continuar notícias pré-release e gestão de posição como camadas auxiliares, nunca substitutos do motor de viés.
**P4 — opcional futuro:** dados caros de opções/fluxo ou intradiários somente após comprovação de benefício e autorização de orçamento.

**Referências de pesquisa para hipóteses (não prova de desempenho do AtlasQuant):**
- BIS sobre atividade carry e transmissão de política para câmbio: https://www.bis.org/publications/bulletin-124-monetary-policy-transmission-exchange-rates-role-currency-carry-trades
- BIS sobre fragmentação e internalização de FX: https://www.bis.org/publications/qr-202512/fx-trade-execution-landscape-through-prism-2025-bis-triennial-survey
- CFTC COT — dados semanais terça/publicação sexta: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- NBER — risco de overfitting ao combinar sinais: https://www.nber.org/papers/w21329

**Governança:** este adendo no Checkpoint Mestre documenta uma decisão de projeto, não a implantação. A PR rascunho #1844 carrega código apenas das duas primeiras camadas e testes sintéticos; a terceira é planejamento, sem modelo calibrado e sem mudança na interface atual.


## Regra confirmada 07/11/2026 — poucos vieses, somente os mais seletivos

**Decisão explícita do proprietário:** AtlasQuant Trader NÃO deve publicar vieses para todo par/consulta. Deve calcular internamente a cobertura G8/28, mas exibir somente hipóteses suficientemente fortes **depois** de comprovadas com dados históricos reais fora da amostra. A prioridade é precisão/expectativa líquida, não quantidade de mensagens; cada viés continua sendo contexto e NÃO ordem de compra/venda. Preservar três abas, W1/D1, M15 como gatilho separado, sem nova despesa.

### Escala editorial aprovada, nunca probabilidade automática

| Nota inteira | Nível editorial | Exposição futura, após homologação |
| --- | --- | --- |
| Sem dados ou 0–5 | INSUFICIENTE | NÃO mostrar viés direcional; AGUARDAR |
| 6 | MODERADO | Candidato selecionado, com todas as provas |
| 7 | FORTE | Candidato selecionado, com todas as provas |
| 8 | ALTO | Candidato selecionado, com todas as provas |
| 9–10 | EXTRA | Candidato selecionado, com todas as provas |

**Nota 8/10 NÃO é 80% de chance de acerto.** A nota representa uma faixa interna a ser definida e empiricamente calibrada; mostrar percentual de acerto apenas se medido, com amostra e intervalo de confiança, estabilidade fora da amostra e sem vazamento. Uma nota de 10 com fontes, regime ou validação incompletos também é **AGUARDAR**.

### Fontes obrigatórias no estudo dos 28 pares

- **Macroeconomia de ambas as moedas:** inflação e sua metodologia/competência; taxa de política e expectativa de mudança; atividade, emprego, surpresas econômicas com consenso *pré-release* verificável; dados oficiais ou provedor licenciado, com vintage e momento de publicação.
- **Microeconomia e microestrutura:** indicadores setoriais/PMIs/produção e crédito, spreads/liquidez disponíveis, influência de commodities/empresas/exportações quando houver fonte confiável e relação mensurável; não inventar ordens ocultas de bancos. A ausência de choque pode ser documentada como NEUTRO; desconhecimento não vira NEUTRO.
- **Geopolítica:** conflitos, sanções, tarifas, comércio, riscos de oferta e políticas governamentais relevantes ao par, com fonte e timestamp confiáveis; distinguir fato de hipótese; contexto não observado fica INDETERMINADO e bloqueia promoção.
- **Regime de mercado:** tendência, lateralização, transição, choque e volatilidade, identificado com informações disponíveis na hora da decisão. Relações e pesos por regime exigem validação histórica independente.
- **Grandes participantes:** COT/TFF CFTC e proxies públicos com o atraso explícito, nunca supor que COT mostra livro de ordens spot nem que posição de terceiros determina cotação.

### Portões e atualização

1. **P0:** completar fontes/competências/vintages das duas moedas e histórico OHLC M15/D1/W1; alinhar horário e qualidade. Sem fundação não há score confiável.
2. **P1:** congelar pré-registro de previsão D1/W1 e definição de acerto; medir por caminhada temporal fora da amostra, taxas de cobertura (abstenção), baselines, Brier/calibração, custo em R e risco. Validar se filtragem 6+ melhora ou piora rendimento líquido e oportunidades.
3. **P2:** experimentar regime + macro relativo; medir ganho incremental ao acrescentar micro e geopolítica sem sinais duplicados por correlação e sem peso inventado; testar COT semanal apenas como contexto.
4. **P3:** só quando calibrado, gerar score seletivo e tier nas telas Início/Radar/Painel Mestre, com explicações e motivo de não emissão. Sem resultado mínimo sustentado, mostrar AGUARDAR e nenhuma porcentagem.
5. **Anti-spam pretendido (LAB):** três consultas econômicas diárias NÃO significam três sinais. Repetição do mesmo viés dentro de 24h para D1 e 7d para W1 fica bloqueada na política candidata; revisitar a regra com validação para eventos extraordinários. Sem mensagens reais ou agendamento ativo.
6. Notícias: manter os dois cálculos já registrados — pré-notícia/nowcast acima/em linha/abaixo do consenso e gestão de posição por evento — como camadas complementares; nunca confundir acerto do CPI com acerto EUR/USD.

**Entrega desta rodada:** `atlasquant_selective_bias_gate_lab.py` e `test_atlasquant_selective_bias_gate_lab.py` na PR rascunho empilhada: a primeira implementa **somente portão de aceitação de um score fornecido pelo chamador**, não calcula score, NÃO testa mercado, e sempre mantém `can_feed_live_radar=False`, `automatic_alert_enabled=False`, `trade_authorized=False`. Os 20 testes sintéticos locais medem contrato do código, NÃO precisão, ganhos nem autenticidade independente. Flags verdadeiras fornecidas pelo chamador não se tornam certificação independente.

**STATUS:** APROVADO COMO REGRA DE PRODUTO; GATE IMPLEMENTADO / EM VALIDAÇÃO SOMENTE LAB; SCORE, FONTES CONFIÁVEIS, CALIBRAÇÃO, BACKTEST OOS E INTEGRAÇÃO PUBLICADA PENDENTES. Sem merge, deploy, Worker, compras, cobrança ou ordens reais.
