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
