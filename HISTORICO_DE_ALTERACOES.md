# Histórico de continuidade

## 16/09/2026 UTC — retomada documentada

- Conferido o Word e preservado seu conteúdo em `docs/continuidade/REGISTRO_ORIGINAL_2026-09-15.md`.
- Verificados GitHub Actions, log de 471 testes e SHAs DEV/main/runtime; diferenças registradas em `CONTEXTO_DO_PROJETO.md`.
- Revisados workflows de coleta e Autopilot, política de branch runtime e gravação de Quota Shadow.
- Preparado plano de ativação, reconciliação, critérios de aceite e rollback, sem executá-lo.
- Entrega exclusivamente documental. A suíte existente pertence a `d6d7779458dbd93735090d1eba45d44418fa672f`; não foi reexecutada para documentação. O filtro de caminhos do workflow não inclui Markdown.
- Pendência imediata: ferramenta de inventário/reconciliação somente leitura em DEV. Promoção continua dependente de autorização específica.

O histórico de desenvolvimento anterior está no registro original e no histórico Git. Não reconstruir commits ou resultados ausentes por suposição.

## 16/09/2026 UTC — auditoria de migração somente leitura

- Ferramenta CLI offline para inventário Git, hashes, presença em cada lado e bloqueios de revisão.
- JSON estrito, detecção de IDs duplicados/conflitantes em registros de primeiro nível, CSV com cabeçalho/largura/linhas repetidas, proteção contra refs locais alteradas.
- Nenhum mecanismo de cópia, remoção, promoção ou chamada ao provedor.
- Nove testes novos aprovados localmente; incluídos no workflow para execução conjunta com os 471 anteriores.
- Auditoria real: nove arquivos, seis diferenças, sete revisões obrigatórias. Resultado preservado em JSON.
- Contexto cumulativo preservado; próxima etapa e limitações descritas em CONTEXTO_DO_PROJETO.md.


## 16/09/2026 UTC — BOS/CHOCH, Order Block e checkpoint ZIP

- Criado workflow \`AtlasQuant DEV Checkpoint\` para produzir ZIP automático do commit exato em cada push da DEV, sem chamadas a provedores e sem tocar runtime.
- Implementado \`ict_structure_v111.py\` com BOS, CHOCH e Order Block rule-based auditável.
- BOS/CHOCH diferencia continuação, mudança de caráter e estrutura mista; não força classificação quando a evidência estrutural é ambígua.
- Order Block exige quebra + displacement + candle oposto de origem; rastreia mitigação/invalidação.
- Integrado ao Institutional Engine, Data Readiness e Central dos 7 pares como camada observacional.
- Pesos do readiness/Gate foram preservados; os componentes novos ainda não autorizam execução por si mesmos.
- Adicionados 5 testes específicos e integração ao Quality workflow.
- GitHub Actions run \`35092388237\`: **485/485 testes OK**, compile gate verde.
- Checkpoint ZIP run \`35092388358\`: sucesso.
- Runtime permaneceu em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main observada em \`b36ba5c457b446ea8b2dfd76f1157ba4af6c52d5\`; nenhuma alteração foi feita nela nesta etapa.


## 16/09/2026 UTC — hardening do novo motor ICT estrutural

- Cobertura adicional para SELL em BOS/CHOCH.
- Cobertura de invalidação de Order Block.
- Cobertura fail-closed para dados insuficientes.
- Regressões de integração de frescor M15 no Data Readiness.
- GitHub Actions run \`35092846046\`: **491/491 testes OK** e compile gate verde.
- Checkpoint ZIP run \`35092846140\`: sucesso.
- Pesos de decisão e Gate permanecem inalterados.


## 16/09/2026 UTC — estrutura resiliente a range/ruído

- ICT Structure Engine atualizado para V1.1.2.
- Tolerância por ATR aplicada a viés estrutural e quebra por fechamento.
- Mesmo swing não pode gerar eventos duplicados após recruzamento.
- Adicionados metadados auditáveis de margem da quebra e tolerância de ruído.
- Novos testes: lateralização, equal-ish pivots, mesmo swing reutilizado e break marginal.
- GitHub Actions run \`35093251163\`: **495/495 testes OK**, compile gate verde.
- Checkpoint ZIP run \`35093251055\`: sucesso.
- Gate/readiness permanecem sem novos pesos nesta etapa.


## 16/09/2026 UTC — Order Block preso à estrutura atual

- ICT Structure Engine atualizado para V1.1.3.
- A quebra estrutural mais recente passou a governar a validade do Order Block.
- Quebra contrária mais nova bloqueia reutilização de zona alinhada antiga.
- Busca de origem limitada à perna estrutural atual, sem atravessar swing/evento anterior.
- Entre múltiplos candles opostos válidos, usa o mais recente antes do displacement.
- Metadados de auditoria adicionados para estrutura, pivô, início da busca e origem.
- Run \`35093608004\` expôs 1 regressão de expectativa em teste legado de invalidação; o teste foi isolado/corrigido sem afrouxar o motor.
- GitHub Actions run \`35093708480\`: **499/499 testes OK**, compile gate verde.
- Runtime e Main não foram alteradas.
- Pesos de Gate/readiness continuam inalterados.


## 16/09/2026 UTC — SELL Order Block + mitigação/reteste

- ICT Structure Engine atualizado para V1.1.4.
- Adicionados \`mitigation_depth_pct\`, \`retest_count\` e \`first_touch_time\`.
- Criado estado específico para mitigação parcial (<50%).
- SELL coberto com múltiplas origens, origem mais recente, mitigação parcial, retestes separados e wick-through.
- Run \`35094093071\` expôs bug na direção da métrica de profundidade para SELL.
- Correção aplicada: BUY mede da borda superior; SELL mede da borda inferior.
- GitHub Actions run \`35094192679\`: **503/503 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.
- Gate/readiness continuam sem novos pesos.


## 16/09/2026 UTC — backtest operacional e planilha

- Criado \`atlasquant_operational_backtest.py\`.
- Criado painel offline \`atlasquant_backtest_panel.py\`.
- Aba Backtest agora aceita OHLC do TradingView + planilha de sinais.
- Adicionados modelos CSV vazios e exportação do ledger completo.
- Métricas: Gain/Loss/BE, Win Rate, R, expectativa, profit factor, drawdown,
  sequências, MFE/MAE, setup e sessão.
- Proteções: anti-look-ahead, geometria BUY/SELL, NO_TRADE em plano inválido e
  LOSS conservador quando stop/alvo são tocados no mesmo candle.
- Backtest legado preservado por compatibilidade.
- GitHub Actions run \`35095699342\`: **518/518 testes OK**, compile gate verde.
- Runtime não foi alterado.


## 16/09/2026 UTC — TradingView Strategy + replay automático

- Criada Strategy Pine BOS/CHOCH + Order Block para o Strategy Tester.
- Painel Backtest passou a disponibilizar download direto do Pine.
- Adicionados testes de presença da estratégia, pivôs confirmados, controles de risco, ausência de primitivas conhecidas de lookahead e processamento no próximo candle.
- Criado \`atlasquant_strategy_replay.py\` para gerar planos automaticamente a partir de OHLC, candle a candle.
- Adicionado bloqueio de operações sobrepostas por par no motor de backtest.
- A aba Backtest agora aceita modo automático com apenas o CSV de candles, além do modo manual com planilha de sinais.
- Replay exporta sinais gerados e ledger completo.
- GitHub Actions run \`35097346652\`: **530/530 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — FVG independente no Backtest e TradingView

- Criado \`atlasquant_fvg_replay.py\`.
- Criada \`tradingview/atlasquant_fvg_strategy_v1.pine\`.
- Aba Backtest ganhou replay FVG separado do BOS/CHOCH + Order Block.
- FVG exporta sinais e ledger próprios; estatísticas não são misturadas.
- Parâmetros: Midpoint/Proximal, stop buffer ATR, alvo R, gap mínimo/ATR, BUY/SELL.
- Workflow de qualidade passou a reagir também a mudanças em \`tradingview/**\`.
- Run \`35097878643\` encontrou 1 falha de contrato textual no comentário do Pine; corrigido sem alterar lógica.
- GitHub Actions run \`35097997003\`: **540/540 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — paridade TradingView/Python

- Criado \`atlasquant_tradingview_parity.py\` para detectar drift estático entre Pine e replay Python.
- Ajustado BOS/CHOCH+OB Pine para validade padrão de 8 candles, igual ao backtest Python.
- Adicionado warmup explícito de 20 candles na Pine BOS/CHOCH+OB.
- Contratos cobrem defaults e fórmulas-chave de FVG e BOS/CHOCH+OB.
- Aba Backtest exibe status da paridade.
- GitHub Actions run \`35098491162\`: **543/543 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — OTE independente no Backtest e TradingView

- Criado `atlasquant_ote_replay.py`.
- Criada `tradingview/atlasquant_ote_strategy_v1.pine`.
- OTE usa zona 62%-79%, sweet spot 70,5%, lookback 28 e extremo recente 12.
- Entrada Sweet 70.5 ou midpoint, stop no swing com buffer ATR e alvo em R.
- Sinal repetido no mesmo impulso é bloqueado; empate BUY/SELL é resolvido de forma determinística pela proximidade ao 70,5%.
- Aba Backtest ganhou bloco OTE separado, Pine próprio, sinais exportáveis e ledger exclusivo.
- Paridade TradingView/Python passou a validar parâmetros e fórmulas centrais do OTE.
- GitHub Actions run `35099427531`: **552/552 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — hardening OTE contra reancoragem

- Replay OTE passou a exigir nova perna estrutural para novo sinal no mesmo lado.
- BUY novo: origem low precisa estar após o terminal high do OTE anterior.
- SELL novo: origem high precisa estar após o terminal low do OTE anterior.
- Extensão do mesmo impulso não cria segundo trade.
- Dois impulsos próximos continuam aceitos quando a nova origem realmente começa após o terminal anterior.
- Adicionados índices de origem/terminal e identificação explícita do re-anchor guard.
- Pine OTE recebeu a mesma regra.
- Paridade TradingView/Python passou a validar o guard.
- GitHub Actions run `35101330822`: **554/554 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — CRT independente no Backtest e TradingView

- Criado `atlasquant_crt_replay.py`.
- Criada `tradingview/atlasquant_crt_strategy_v1.pine`.
- CRT usa sequência anchor range → raid/reclaim → directional delivery.
- BUY/SELL são medidos separadamente, com entrada no delivery close, stop na varredura/anchor e alvo na borda oposta do range.
- Adicionados buffer ATR opcional e filtro de RR mínimo.
- Aba Backtest ganhou bloco CRT independente, Pine próprio, sinais exportáveis e ledger separado.
- Paridade TradingView/Python passou a verificar regras e defaults centrais do CRT.
- GitHub Actions run `35101892468`: **564/564 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — AMD / Power of Three independente

- Criado `atlasquant_amd_replay.py`.
- Criada `tradingview/atlasquant_amd_strategy_v1.pine`.
- AMD usa máquina de estados rígida: Acumulação → Manipulação → Distribuição.
- Range de acumulação é congelado antes da manipulação.
- Distribuição só pode confirmar em candle posterior e também precisa superar o fechamento da manipulação no lado esperado.
- Adicionadas expiração da manipulação, buffer ATR, RR mínimo e alvos estruturais na borda oposta da acumulação.
- Sweep nos dois lados é resolvido de forma determinística pela profundidade normalizada.
- Aba Backtest ganhou bloco AMD separado, Pine próprio, sinais exportáveis e ledger exclusivo.
- Paridade TradingView/Python passou a validar os contratos centrais do AMD/PO3.
- Primeiro run encontrou 1 teste com expectativa mais frouxa que a regra do motor; teste corrigido sem afrouxar a lógica.
- GitHub Actions run `35102692080`: **576/576 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — comparador dos 5 operacionais

- Criado `atlasquant_strategy_comparator.py`.
- Comparador executa BOS/CHOCH+OB, FVG, OTE, CRT e AMD no mesmo histórico, mantendo resultados separados.
- Métricas por estratégia: trades, gain/loss/BE, win rate, expectativa R, net R, profit factor, drawdown, streak de loss e ambiguidades OHLC.
- Adicionada classificação descritiva de tamanho de amostra.
- Ranking observado só é liberado acima de um mínimo configurável de trades (padrão 20).
- Estratégias com amostra pequena continuam visíveis, mas sem posição no ranking.
- Adicionados breakdown por sessão e ledger combinado com identidade da estratégia preservada.
- Aba Backtest ganhou bloco **Comparador dos 5 operacionais** e exportações CSV.
- GitHub Actions run `35103238881`: **582/582 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — estabilidade temporal no comparador

- Criado `atlasquant_strategy_stability.py`.
- Cada um dos 5 operacionais passa a ser analisado em blocos cronológicos independentes.
- Suporte a 3, 4 ou 5 blocos.
- Métricas por bloco: trades, gain/loss/BE, win rate, expectativa R, net R, drawdown e streak de loss.
- Status descritivos: `POSITIVE_ACROSS_FOLDS`, `NEGATIVE_ACROSS_FOLDS`, `MIXED_ACROSS_FOLDS` e `INSUFFICIENT`.
- Estratégias sem amostra mínima por bloco não recebem leitura de estabilidade.
- Aba Backtest ganhou tabela de estabilidade, detalhe dos blocos e exportação CSV.
- GitHub Actions run `35103716697`: **588/588 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — walk-forward no comparador dos 5 operacionais

- Criado `atlasquant_strategy_walkforward.py`.
- Implementado walk-forward cronológico com treino expansivo e janelas OOS posteriores.
- Sem otimização automática: regras e parâmetros dos setups ficam fixos.
- Configurações: treino inicial 50/60/70% e 2/3/4 janelas OOS.
- Métricas por janela: trades, expectativa R, net R, win rate, drawdown, streak de loss e delta teste-treino.
- Resumo por estratégia: `POSITIVE_ALL_OOS_WINDOWS`, `NEGATIVE_ALL_OOS_WINDOWS`, `MIXED_OOS_WINDOWS` ou `INSUFFICIENT`.
- Aba Backtest ganhou controles, resumo, detalhe e exportação CSV de walk-forward.
- GitHub Actions run `35104652826`: **595/595 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas por esta etapa.


## 16/09/2026 UTC — custos e slippage no Backtest

- Motor de backtest passou a aceitar `slippage_r` além de `cost_r`.
- Resultado líquido agora registra `gross_r`, `cost_r`, `slippage_r`, `total_friction_r` e `net_r`.
- Fricção inválida/negativa falha fechado.
- Criado `atlasquant_strategy_friction.py` para reprecificar os mesmos trades sob cenários diferentes de atrito.
- Cenários não regeneram sinais nem mudam caminho estrutural do trade.
- Resumo mostra quando a expectativa permanece positiva em todos os cenários, quebra sob stress, já nasce não positiva ou tem amostra insuficiente.
- Aba Backtest ganhou input de slippage, stress configurável, tabela detalhada e exportação CSV.
- Todos os cinco operacionais, comparador e backtest manual agora recebem custo + slippage.
- GitHub Actions run `35105537324`: **605/605 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas por esta etapa.


## 16/09/2026 UTC — robustez segmentada e grade fixa de parâmetros

- Sensibilidade de custos/slippage passou a ter breakdown por sessão e por par.
- Adicionada exportação CSV do stress segmentado.
- Criado `atlasquant_strategy_parameter_robustness.py`.
- Grade pré-definida testa 3 variantes por cada um dos 5 operacionais, total de 15 variantes.
- Não existe otimização, auto-seleção, ranking de parâmetros ou promoção automática.
- BOS/CHOCH+OB: 1,5R / 2,0R / 2,5R.
- FVG: gap mínimo 0 / 0,10 / 0,20 ATR.
- OTE: Sweet 70,5 / Zone Midpoint / impulso mínimo 0,50 ATR.
- CRT: RR mínimo 0 / 0,50 / 1,00.
- AMD/PO3: acumulação 6 / 8 / 10 candles.
- UI ganhou opção explícita de ativar robustez, tabela resumida/detalhada e exportação CSV.
- Robustez fica desativada por padrão para evitar custo desnecessário em históricos longos.
- GitHub Actions run `35106389108`: **615/615 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.


## 16/09/2026 UTC — relatório consolidado de evidências

- Criado `atlasquant_backtest_evidence.py`.
- Backtest geral, estabilidade temporal, walk-forward, custos/slippage e robustez de parâmetros passam a ser consolidados em uma única visão.
- Cobertura de diagnósticos é separada de performance e usa apenas `COMPLETE`, `PARTIAL` e `INSUFFICIENT`.
- Robustez de parâmetros não executada fica `NOT_RUN`; nenhuma conclusão é inventada.
- Relatório não cria score, ranking, recomendação, previsão ou probabilidade de lucro.
- UI ganhou tabela **Relatório consolidado de evidências**.
- Adicionadas exportações JSON auditável e Markdown resumido.
- JSON usa schema `ATLASQUANT_BACKTEST_EVIDENCE_V1` e flags explícitas de pesquisa-only/no-Gate/no-probability.
- GitHub Actions run `35107095265`: **622/622 testes OK**, compile gate verde.
- Runtime/Main não foram alteradas.
