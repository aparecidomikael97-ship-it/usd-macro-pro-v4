# Registro original de continuidade recebido do usuário

Fonte: AtlasQuant_Documento_Continuidade_2026-09-15 (1).docx. Texto preservado em ordem, incluindo tabelas. Este é um registro histórico; consultar CONTEXTO_DO_PROJETO.md para verificações posteriores.

AtlasQuant — Documento de Continuidade

Handoff detalhado para continuar o projeto em uma nova conversa

Atualizado em 15/09/2026 (horário do usuário)

| ESTADO VERIFICADO NO GITHUB / Branch DEV: atlasquant-dev @ d6d7779458dbd93735090d1eba45d44418fa672f / Último workflow: 35047014369 — sucesso / Testes: 471/471 OK + compile gate verde / Main: cffc85c2d89f30137c274c88629bc01bd6b1c3a8 / Runtime: atlasquant-runtime @ 2432a32833426f53cf834d2245ac3bf2ce10a5a1 |
| --- |

| REGRA DE OURO DO HANDOFF / Continuar o desenvolvimento em atlasquant-dev. Antes de afirmar progresso, buscar o estado real do GitHub Actions. Não fazer merge para main, promoção para produção ou alteração destrutiva de dados/credenciais sem autorização específica do usuário. |
| --- |

## Índice de continuidade

1. Resumo executivo e visão do produto

2. Objetivos funcionais e experiência desejada

3. Regras, autonomia e decisões combinadas

4. Arquitetura atual e fluxo de dados

5. Repositório, branches e situação de divergência

6. O que está implementado — por camada

7. Expansão 7 → 28 pares e pesquisa 28FX

8. Testes, CI e qualidade

9. Dados, fontes e política de quota

10. Decisões justificadas e ideias descartadas

11. O que ainda é planejado / não concluído

12. Problemas pendentes e riscos

13. Próximos passos recomendados

14. Instruções exatas para retomar em nova conversa

15. Apêndice — caminhos e módulos importantes

## 1. Resumo executivo e visão do produto

O projeto começou como USD Macro Pro e está evoluindo para o AtlasQuant — Market Intelligence Platform, uma plataforma de análise direcional de mercado em Streamlit/GitHub com foco principal em Forex. A visão é combinar macroeconomia, bancos centrais, juros, notícias, intermarket, força relativa, ICT/Smart Money, qualidade/frescor de dados, Safety Core, backtest/forward-test, Journal/Flight Recorder, Shadow Mode e validação contínua.

IMPLEMENTADO: um núcleo DEV robusto, auditável e fail-closed, com 471 testes automatizados verdes.

AINDA NÃO FINALIZADO: a promoção para main/produção, a ativação real da branch runtime, a coleta persistente de evidência Shadow/Quota em ambiente ativo e a expansão técnica real para 28 pares.

### Princípio operacional central

| MACRO = direção \| ICT/SMC = onde/quando \| RISCO = quando não operar e quanto expor / A plataforma não deve fabricar entradas nem transformar um score interno em “probabilidade de lucro”. Dados ausentes, antigos, conflitantes ou insuficientes devem resultar em espera, neutralidade ou bloqueio. |
| --- |

## 2. Objetivos funcionais e experiência desejada

### Central / Home

Mostrar “Melhores oportunidades agora” com BUY / SELL / NEUTRAL / NÃO OPERAR.

Semáforo operacional: 🟢 procurar entrada, 🟡 aguardar, 🔴 não operar.

Ranking do universo Forex, com evolução para 28 pares G8.

Força da moeda base versus cotada.

Explicação: “Por que o AtlasQuant está dizendo isso?”.

Confluence Map: Macro, Rates, Banco Central, News, Intermarket, ICT/SMC, dados e Gate.

Qualidade/frescura dos dados visível.

Próximo evento macro e risco de invalidação.

Safety Core independente.

Journal / Flight Recorder, Backtest, Performance Lab e Validation Readiness.

### Modo Básico e Modo Pro

| Modo | Objetivo | Conteúdo principal |
| --- | --- | --- |
| Básico | Decisão rápida e limpa | Direção, Safety Core, próximo evento, cards operacionais, plano, mesa rápida. |
| Pro | Diagnóstico institucional | Qualidade, regime, confluência, explicações, Flight Recorder, matrizes e labs detalhados. |

A ordem de informação definida para a experiência é: 1) o que está acontecendo; 2) qual direção; 3) quão confiáveis são os dados; 4) por quê; 5) o que falta para entrar; 6) o que pode invalidar.

## 3. Regras, autonomia e decisões combinadas

### Autonomia concedida pelo usuário

O usuário autorizou melhorias autônomas na DEV quando elas aumentarem qualidade, segurança, utilidade, arquitetura, testes, UX, performance, dados, logging, backtest/calibração/shadow ou cobertura.

Pode corrigir defeitos e continuar sem esperar “vamos lá” quando houver uma próxima melhoria segura e clara.

Mudanças de motor/modelo ficam primeiro em DEV e devem ser testadas.

Pode refatorar e organizar desde que preserve o comportamento crítico e a rastreabilidade.

### Hard stops — exigem autorização específica

Merge de atlasquant-dev para main.

Promoção para produção.

Alteração destrutiva de dados persistentes.

Alteração de credenciais/secrets.

### Regras técnicas obrigatórias

Nunca afirmar que testes passaram sem verificar o workflow/log real.

Diferenciar claramente: planejado → implementado → testado → aprovado.

Não prometer trabalho em background; o trabalho ocorre apenas quando uma execução/turno está ativo.

Sem garantia de 90% de acerto, lucro ou win rate.

Score/convicção internos não são probabilidade de lucro, salvo calibração explícita e validada.

Fail-closed: dado crítico ausente/antigo/conflitante → não operar/aguardar.

Não inventar horários de evento, countdown, entrada, stop, alvo ou probabilidade.

Não fazer chamadas Twelve Data apenas porque a UI foi aberta; a UI deve consumir cache/estado persistente.

## 4. Arquitetura atual e fluxo de dados

Fluxo conceitual consolidado: Dados → reconciliação de fontes → frescor → Macro → surpresa econômica → bancos centrais → rates → news → geopolitics/intermarket → regime → força relativa → pares → consenso → qualidade → Safety Core → ICT/SMC → plano operacional → ranking → Journal/Flight Recorder → Shadow → Performance/Calibration/Stability → Validation Readiness.

### Camadas principais

| Camada | Responsabilidade | Status |
| --- | --- | --- |
| Motor base | Macro, força, matriz, 7 pares institucionais | IMPLEMENTADO |
| AtlasQuant Foundation | Universo 28 G8, consenso, confidence, safety, journal | IMPLEMENTADO |
| Central | Cards, brief, quality, regime, confluência, plano, Basic/Pro | IMPLEMENTADO |
| Runtime persistence | Separar dados mutáveis do código | IMPLEMENTADO EM DEV |
| Shadow / Challenger | Champion × Challenger persistente e balanceado por par | IMPLEMENTADO EM DEV |
| Validation Labs | Performance, Calibration, Stability, Readiness, Evidence Bundle | IMPLEMENTADO |
| 28FX research | Adaptive coverage, M15→H1/H4, execution gate, quota shadow | IMPLEMENTADO COMO PESQUISA |
| 28FX live pipeline | Coleta/execução técnica real dos 28 | NÃO ATIVADO |
| Índices/WIN/WDO | Motores específicos | PLANEJADO |

## 5. Repositório, branches e situação de divergência

Repositório: aparecidomikael97-ship-it/usd-macro-pro-v4

Branch de desenvolvimento: atlasquant-dev

Branch principal: main

Branch de runtime: atlasquant-runtime

| Branch | SHA verificado | Papel |
| --- | --- | --- |
| atlasquant-dev | d6d7779458dbd93735090d1eba45d44418fa672f | Desenvolvimento ativo / 471 testes verdes |
| main | cffc85c2d89f30137c274c88629bc01bd6b1c3a8 | Código/produção atual; não tocar sem autorização |
| atlasquant-runtime | 2432a32833426f53cf834d2245ac3bf2ce10a5a1 | Destino dedicado para dados mutáveis, ainda não ativo em produção |

### Divergência atual

Comparação main → atlasquant-dev: a DEV está 191 commits à frente e 65 commits atrás. A verificação reversa mostrou que esses 65 commits do lado main alteram somente sete arquivos de runtime em dados/: autopilot_inputs, autopilot_status, configuracoes_completas, currency_news_current, currency_news_validation, master_market_map e scanner_tecnico.

| INTERPRETAÇÃO IMPORTANTE / A divergência “atrás” não representa 65 mudanças de código que precisam ser trazidas para a DEV. É churn de dados operacionais gravados na main. A separação para atlasquant-runtime foi implementada na DEV, mas ainda não foi promovida para main; portanto os workflows ativos da main continuam escrevendo dados na main. |
| --- |

### Arquivos de runtime dedicados ainda não confirmados na branch runtime

Na checagem deste handoff, os seguintes arquivos ainda retornavam 404 em atlasquant-runtime, o que significa que a persistência nova não foi ativada/gerada ali em ambiente real:

Pendente de criação real: dados/atlasquant_shadow_samples.jsonl

Pendente de criação real: dados/atlasquant_flight_recorder.jsonl

Pendente de criação real: dados/atlasquant_quota_shadow_v1.json

## 6. O que está implementado — por camada

### 6.1 Fundação AtlasQuant

| Arquivo | Função |
| --- | --- |
| atlasquant_fx_universe.py | Universo G8, 28 crosses, direção e diferencial relativo. |
| atlasquant_safety_core.py | Veto independente fail-closed; só permite, alerta, espera ou bloqueia. |
| atlasquant_data_confidence.py | Golden Record e reconciliação de fontes numéricas. |
| atlasquant_consensus.py | Agregação por grupos independentes para reduzir double-counting. |
| atlasquant_journal.py | Registros de decisão, bloqueio, resultado e métricas em R. |
| atlasquant_release_guard.py | Guardrails de release/rollback; promoção automática proibida. |

### 6.2 Central institucional e experiência

atlasquant_dashboard_v1.py — radar macro G8 de 28 pares e cards de foco.

atlasquant_coverage_funnel.py — deixa explícito: 28 pares têm radar macro; apenas 7 têm pipeline completo.

atlasquant_central_brief.py — resumo executivo de saúde/execução.

atlasquant_data_quality_center.py — qualidade e frescor.

atlasquant_context_explain.py — explica mudanças entre snapshots.

atlasquant_confluence_map.py — mapa descritivo das camadas de evidência.

atlasquant_operational_plan.py — plano sem inventar entrada/stop.

atlasquant_safety_panel.py — ponte dos dados live para Safety Core.

atlasquant_regime_detector.py — detecta transição/shift sem prever preço.

atlasquant_ui_v1.py — design system e estrutura visual.

Modo Básico foi simplificado sem desligar Safety, evento, regime-capture ou Flight Recorder.

### 6.3 Próximo evento macro estruturado

IMPLEMENTADO: atlasquant_next_event.py + integração com Central e Safety Core.

Regra: countdown só é calculado quando existe timestamp estruturado. Se houver apenas data, o sistema mostra “horário não estruturado” e não inventa minutos. Quando há timestamp exato de evento de alto impacto, os minutos podem alimentar o buffer do Safety Core.

### 6.4 Flight Recorder persistente

atlasquant_flight_recorder_panel.py — captura em modo Básico e Pro, deduplicação e hidratação.

atlasquant_flight_recorder_store.py — JSONL persistente, conflito de escrita, fail-closed em branch de código.

Persistência foi preparada para atlasquant-runtime; arquivo real ainda não foi criado na branch runtime verificada.

### 6.5 Separação de runtime

atlasquant_runtime_store.py — resolve branch de dados e redireciona main/atlasquant-dev para atlasquant-runtime.

atlasquant_branch_drift.py — classifica divergência de runtime versus código/config.

Autopilot, Market Map, Master Panel, Pair Intelligence, news validation e workflows foram adaptados na DEV.

A mudança é segura em DEV, mas não está ativa nos workflows da main enquanto não houver promoção autorizada.

### 6.6 Labs de pesquisa e validação

atlasquant_calibration_lab.py — relação score × resultado observado por bandas; não transforma score em probabilidade.

atlasquant_performance_lab.py — métricas históricas por horizonte/dimensão.

atlasquant_stability_lab.py — folds temporais, sessões e estabilidade walk-forward descritiva.

atlasquant_validation_readiness.py — combina Performance, Calibration, Stability e Shadow.

atlasquant_evidence_bundle.py — manifesto JSON auditável com hash SHA-256 para revisão humana.

O histórico de pesquisa foi otimizado para uma única leitura persistente por rerun na aba Melhorias.

### 6.7 Shadow Mode e Challenger

atlasquant_challenger_v1.py — Challenger StrictGate V1, observacional.

O Challenger nunca autoriza um trade que o Champion não tenha autorizado.

atlasquant_shadow_capture.py — captura os 7 pares, hidrata sessão + runtime e persiste amostras.

atlasquant_shadow_store.py — armazenamento JSONL em runtime, dedupe e proteção contra corrupção/conflito.

atlasquant_shadow_mode.py — comparação Champion × Challenger, divergências críticas, cobertura por par.

Critério implementado: mínimo global padrão 100 amostras e mínimo padrão 10 por cada um dos 7 pares, com zero divergências críticas para ficar elegível apenas para revisão manual.

Auto-promoção continua desativada por design.

## 7. Expansão 7 → 28 pares e pesquisa 28FX

### O que já existe

O radar macro de 28 pares já existe. O pipeline institucional/técnico completo continua limitado aos 7 majors USD (EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/JPY, USD/CHF, USD/CAD). A expansão para 28 está sendo tratada como projeto de infraestrutura e validação, não como simples alteração de PAIR_ORDER.

### Plano adaptativo implementado

| Parâmetro padrão | Valor | Observação |
| --- | --- | --- |
| Universo | 28 pares | G8 |
| Conjunto ativo | 3 pares | Somente ativos podem chegar a execution-grade |
| M15 ativo | ~55 min | Planejamento |
| M15 background | ~180 min | Contexto; não execução |
| Cap Twelve | 480/dia | Política interna conservadora |
| Reserva | 80 calls | Cap utilizável = 400 |
| Estimativa teórica | 309 calls/dia | Com defaults atuais |
| Folga teórica | 91 calls | 309 dentro de 400 |
| Histórico M15-alvo | 1000 barras | Planejamento de cobertura |

Esse cálculo é teórico. Ele não autoriza expansão live. O próprio módulo marca live_change_allowed=False, automatic_expansion_allowed=False e manual_validation_required=True.

### Derivação H1/H4 a partir de M15

atlasquant_m15_derived_timeframes.py foi implementado como utilitário de pesquisa.

H1 usa exatamente 4 candles M15 completos e contíguos; H4 usa exatamente 16.

Grupos parciais são descartados.

O módulo não faz chamadas de API e não altera comportamento live.

### Gate adaptativo de execução

atlasquant_adaptive_execution_gate.py é fail-closed.

Par fora do active set = contexto apenas, nunca execution-grade.

Par ativo ainda precisa M15 fresco, H1/H4 derivados prontos, grupos completos, dados suficientes e nenhum hard block.

Live wiring automático continua proibido.

### Quota Shadow

atlasquant_quota_shadow.py coleta evidência observacional de consumo real versus plano 28FX.

Integrado ao Autopilot DEV e ao painel Autopilot DEV.

Critério padrão: pelo menos 20 rodadas com mercado aberto, sem bloqueios do provedor, sem falhas headless e plano cabendo no cap em todas as amostras.

Mesmo após atingir critério, apenas revisão manual é permitida; auto-expansão permanece desligada.

Na branch runtime verificada ainda não existia dados/atlasquant_quota_shadow_v1.json; portanto a evidência real ainda precisa ser acumulada após ativação.

## 8. Testes, CI e qualidade

| BASELINE ATUAL VERIFICADO / GitHub Actions run 35047014369 — “AtlasQuant 28FX: include quota shadow panel regression tests” / Resultado: SUCCESS / 471 testes executados, 471 OK / Compile gate: verde / Head SHA: d6d7779458dbd93735090d1eba45d44418fa672f |
| --- |

### Quality workflow

.github/workflows/quality-tests.yml roda compileall antes dos testes.

Workflow dispara para branches main e atlasquant-dev em mudanças relevantes.

A suíte inclui testes legados do motor e testes novos de AtlasQuant: safety, UI, central, coverage, performance, stability, shadow, persistence, 28FX, quota shadow e contratos de branch.

Falhas históricas de sintaxe foram detectadas pelo compile gate e corrigidas; isso justificou manter a compilação como gate permanente.

## 9. Dados, fontes e política de quota

### Fontes / integrações conhecidas

FRED — séries macro e datas de releases.

EODHD — tentativa de economic events/consenso quando disponível.

Google News RSS / NewsAPI — notícias e sentimento por moeda.

Twelve Data — OHLC e dados técnicos.

GitHub — persistência de cache, estados, histórico e workflows.

### Política Twelve Data

Budget persistente e fail-closed.

Cap interno conservador de 480 créditos/dia.

Limites de ritmo por minuto/janela são tratados separadamente de quota diária.

Falhas/timeouts são tratados conservadoramente.

Cache e candles fechados são validados; dado stale não pode ser relabelado como fresh.

Abrir a UI não deve provocar refresh externo do provedor.

### Observação operacional importante

O histórico anterior mostrou HTTP 429 por quota/minute limit. A arquitetura atual responde bloqueando novas chamadas quando necessário e agora adiciona Quota Shadow para provar, com amostra real, se a arquitetura 28FX cabe no orçamento.

## 10. Decisões justificadas e ideias descartadas

| Decisão / ideia | Status | Justificativa |
| --- | --- | --- |
| Expandir 7→28 apenas mudando PAIR_ORDER | DESCARTADO | Estoura orçamento/frescor e criaria falso execution-grade. |
| 28 pares com mesma cadência dos 7 | DESCARTADO | Planejador antigo mostra que o cap é insuficiente. |
| Arquitetura 28 com active set + background | MANTIDA EM PESQUISA | Permite preservar contexto sem liberar todos como executáveis. |
| Derivar H1/H4 de M15 | IMPLEMENTADO COMO PESQUISA | Reduz chamadas; exige grupos completos e validação. |
| Auto-promoção do Challenger | PROIBIDO | Risco de regressão; somente revisão humana. |
| Score = probabilidade de lucro | PROIBIDO | Só pode virar probabilidade após calibração válida e explícita. |
| Inventar horário/countdown de evento | PROIBIDO | Safety exige timestamp estruturado. |
| Gravar runtime em main | SUBSTITUIR | Causa divergência artificial e mistura código com dados mutáveis. |
| Merge automático para main | PROIBIDO | Hard stop acordado com o usuário. |
| Reusar pesos FX em índices/WIN/WDO | DESCARTADO | Ativos precisam motores específicos. |
| Central Básica cheia de painéis técnicos | REDUZIDO | Basic deve responder decisão; Pro concentra diagnóstico. |

## 11. O que ainda é planejado / não concluído

| Item | Situação atual | O que falta |
| --- | --- | --- |
| Runtime dedicado em produção | Código DEV pronto | Promoção autorizada para main e execução real dos workflows. |
| Flight Recorder persistente real | Store/hidratação implementados | Arquivo runtime ainda não criado; acumular histórico real. |
| Shadow real persistente | Captura/store/Challenger implementados | Acumular amostras; 100 total + 10/par, sem critical mismatch. |
| Quota Shadow real | Telemetria implementada | Acumular ≥20 market-open runs e validar sem blocks/falhas. |
| 28 pares técnicos live | Pesquisa e gates implementados | Validar resampling, active-set freshness e quota; só depois discutir wiring live. |
| Índices EUA | Planejado | Criar motores asset-specific para S&P, Nasdaq, Dow. |
| WIN / WDO | Planejado | Motores próprios, sem reciclar cegamente lógica FX. |
| Academy / vídeos | Planejado e confirmado | Produzir depois que telas/fluxo estabilizarem. |
| AI Copilot | Planejado | Definir escopo, contexto e guardrails após core estável. |
| Staging / produção / rollback | Guardrails de release existem | Processo operacional final e promoção controlada. |

### Vídeos / Academy — compromisso mantido

O usuário confirmou que os vídeos continuam no plano. A decisão foi produzi-los depois da estabilização da interface, para evitar tutoriais de telas que ainda mudam.

Macroeconomia para Forex.

CPI / PCE / NFP / PMI e leitura de surpresa.

Fed, juros e narrativa hawkish/dovish.

Comparação EUR × USD e força das 8 moedas.

Calendário econômico / Investing.

ICT/SMC depois da direção macro.

Como usar os painéis do AtlasQuant.

## 12. Problemas pendentes e riscos

A main continua recebendo commits de dados runtime; isso continuará até a separação ser promovida.

atlasquant-runtime existe, mas os novos arquivos persistentes de Shadow/Flight/Quota ainda não foram observados nela.

Não há ainda amostra real suficiente para declarar Shadow, Calibration, Stability ou Quota como maduros para revisão final.

A expansão 28FX continua research-only; nenhum novo par deve ser marcado executável só porque o radar macro existe.

Mudanças recentes são grandes em relação à main (191 commits à frente); um futuro merge exige revisão cuidadosa e provavelmente estratégia de reconciliação de runtime.

APP_VERSION ainda aparece como 11.0.8 — STRENGTH ATTRIBUTION + AUDIT INTEGRITY · MOTOR BASE V9.3.9.2; não renomear em massa sem necessidade.

O contrato literal de tabs em usd_macro_pro_v4_cloud.py deve ser preservado enquanto testes legados dependerem dele.

## 13. Próximos passos recomendados

Verificar sempre o GitHub Actions antes de qualquer novo bloco; baseline atual = 471/471.

Manter atlasquant-dev como única branch de desenvolvimento.

Não fazer merge ainda. Primeiro preparar uma estratégia de ativação da separação runtime em main sem perder os dados atuais.

Depois de autorização de promoção, fazer os workflows da main escreverem em atlasquant-runtime e confirmar criação de Flight/Shadow/Quota files.

Acumular evidência real: Flight Recorder, Shadow Mode e Quota Shadow.

Somente quando Quota Shadow + M15→H1/H4 + active-set gate estiverem validados, considerar experimento controlado de 28FX live.

Continuar a Validation Readiness com amostras reais e usar o Evidence Bundle para revisão humana.

Após o core Forex estabilizar: finalizar UX e então produzir Academy/vídeos.

Índices/WIN/WDO apenas em motores separados depois do Forex.

### Próxima melhoria segura se ainda não houver autorização de merge

Trabalhar apenas em DEV em validação, instrumentação e testes. Evitar qualquer mudança que dependa de dados reais da runtime até a ativação da branch dedicada. Bons alvos: reforçar Evidence Bundle, melhorar diagnósticos de quota/shadow, testar migração/reconciliação e preparar um plano de promoção sem executá-lo.

## 14. Instruções exatas para retomar em nova conversa

| PROMPT DE RETOMADA RECOMENDADO / “Continue o projeto AtlasQuant usando este documento como fonte de verdade. Antes de alterar qualquer coisa, verifique o estado atual do GitHub Actions e as SHAs de main, atlasquant-dev e atlasquant-runtime. Trabalhe somente em atlasquant-dev. Não faça merge para main, promoção para produção ou alteração destrutiva sem minha autorização específica. Preserve o Safety Core fail-closed, não invente dados/eventos/entradas e mantenha score separado de probabilidade de lucro. Se a baseline mudou, me diga exatamente o que mudou antes de prosseguir.” |
| --- |

### Ao receber “chat progresso”

Buscar latest GitHub Actions da atlasquant-dev.

Informar contagem real de testes e compile status.

Informar SHA DEV atual.

Resumir apenas mudanças novas relevantes.

Se necessário, comparar main/dev e distinguir runtime-data drift de code drift.

### Ao receber “vamos lá”

Prosseguir com a próxima melhoria segura na DEV, sem pedir confirmação para tarefas já cobertas pela autonomia. Parar apenas nos hard stops.

## 15. Apêndice — caminhos e módulos importantes

### Arquivos centrais

Aplicação principal: usd_macro_pro_v4_cloud.py

Pipeline institucional 7 pares: pair_intelligence_v110.py

Autopilot: autopilot_v107.py

Painel Autopilot: autopilot_panel_v107.py

Workflow Autopilot: .github/workflows/autopilot-v107.yml

Workflow qualidade: .github/workflows/quality-tests.yml

Coleta automática: .github/workflows/coleta_automatica.yml

Budget Twelve: twelve_budget_v1108.py

Cache Twelve: twelve_cache_v1108.py

### Arquivos de dados runtime atuais/legados

Runtime legado: dados/autopilot_inputs_v107.json

Runtime legado: dados/autopilot_status_v107.json

Runtime legado: dados/configuracoes_completas_v937.csv

Runtime legado: dados/currency_news_current_v107.json

Runtime legado: dados/currency_news_validation_v1061.csv

Runtime legado: dados/master_market_map_v102.json

Runtime legado: dados/scanner_tecnico_v934.json

### Novos stores/pesquisa

Runtime dedicado planejado/implementado em código: dados/atlasquant_flight_recorder.jsonl

Runtime dedicado planejado/implementado em código: dados/atlasquant_shadow_samples.jsonl

Runtime dedicado planejado/implementado em código: dados/atlasquant_quota_shadow_v1.json

### Módulos AtlasQuant recentes

Módulo: atlasquant_adaptive_coverage.py

Módulo: atlasquant_adaptive_execution_gate.py

Módulo: atlasquant_branch_drift.py

Módulo: atlasquant_challenger_v1.py

Módulo: atlasquant_evidence_bundle.py

Módulo: atlasquant_flight_recorder_panel.py

Módulo: atlasquant_flight_recorder_store.py

Módulo: atlasquant_m15_derived_timeframes.py

Módulo: atlasquant_next_event.py

Módulo: atlasquant_quota_shadow.py

Módulo: atlasquant_runtime_store.py

Módulo: atlasquant_shadow_capture.py

Módulo: atlasquant_shadow_mode.py

Módulo: atlasquant_shadow_store.py

Módulo: atlasquant_validation_readiness.py

### Contrato de navegação que deve ser preservado

Em usd_macro_pro_v4_cloud.py, a declaração literal atual é:

| abas = st.tabs([ /     "Central", "Painel mestre", "Moedas", "EUA", "Pares", "Fed", /     "Histórico", "Backtest", "Decisão", "Market Map", "Aprender", /     "Produto", "Melhorias", "Notícias", "Autopilot", / ]) |
| --- |

### Último estado confirmado

| Campo | Valor |
| --- | --- |
| DEV SHA | d6d7779458dbd93735090d1eba45d44418fa672f |
| Main SHA | cffc85c2d89f30137c274c88629bc01bd6b1c3a8 |
| Runtime SHA | 2432a32833426f53cf834d2245ac3bf2ce10a5a1 |
| Run ID | 35047014369 |
| Resultado | 471/471 testes — OK |
| Título do run | AtlasQuant 28FX: include quota shadow panel regression tests |
| App version string | 11.0.8 — STRENGTH ATTRIBUTION + AUDIT INTEGRITY · MOTOR BASE V9.3.9.2 |

| FIM DO HANDOFF / Este documento diferencia explicitamente o que já foi implementado do que ainda depende de ativação, amostra real, autorização de merge ou desenvolvimento futuro. Em caso de conflito entre este documento e o repositório, o estado atual do GitHub deve prevalecer após verificação. |
| --- |
