# AtlasQuant — Reconciliação paralela do Checkpoint Mestre e do Trader
**Data:** 22/10/2026 · **Natureza:** inventário documental, não implementação nem homologação

## Propósito e isolamento
A missão original do AtlasQuant é um painel pessoal de inteligência de mercado Forex: indicar **cenários e vieses fundamentados para o dia, a semana e o mês**, com força relativa das moedas, macroeconomia, bancos centrais, geopolítica e validação técnica. AION atua como **orquestrador seguro** desse ecossistema. Negócios e Investimentos são extensões com prioridades próprias. Capacidades futuras de criação de vídeo, imagem, programação autônoma e comercialização de IA não são pré-requisitos do núcleo.

Esta reconciliação foi escrita em ramo documental isolado criado a partir de **main**, sem tocar nas PRs Draft de segurança A176–A183, sem merge/deploy/Worker, novas APIs ou gasto. **P0 homologados: 0/6; HARD NO-GO.**

## Fontes primárias verificadas diretamente na main
1. `docs/continuidade/REGISTRO_ORIGINAL_2026-09-15.md`: origem Forex; regra MACRO=direção, ICT/SMC=localização/gatilho, risco=quando não operar; radar macro G8 de 28 pares com apenas sete majors USD no pipeline institucional completo àquela data; pesquisa 28FX não implica 28 pares executáveis.
2. `docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md`: fonte principal do produto; separação de viés macro e ordem; promoção Laboratório→Backtest/OOS/Walk-Forward→Shadow→Paper/Forward; calendário, briefing, Academy, Investimentos.
3. `docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md`: decisões posteriores complementam, não apagam o checkpoint anterior; AION núcleo central único e persistência oficial; ADR e ATR distintos; prioridades e gates de implementação.
4. `docs/continuidade/AION_HISTORICAL_COMMITMENTS_2026-10-02.md`: registro de decisões com estados distintos; Radar 28FX + TOP10 e briefing macro texto/voz **aprovados/pendentes**; fundação do laboratório/radar **implementada/em validação**; Elliot descartado; automação real adiada.

**Fontes de reconciliação adicionais:** decisões das conversas do proprietário de 03/10–22/10, incluindo Economia Global (08/10), Radar Eleições/Eventos/Liquidez (08/10), UX quatro cards e Trader compacto (03/10–12/10), e retorno explícito do Trader à centralidade funcional (22/10). Essas decisões estão aqui como **histórico conversacional ainda a persistir/validar**, não como alegação de implementação no repositório.

## Inventário de requisitos do Trader

| ID | Requisito e critério de aceite futuro | Evidência atual | Estado honesto |
|---|---|---|---|
| T01 | Visão diária, semanal e mensal de regime, viés e cenário invalidante para Forex | Checkpoint 22/09; compromissos 02/10; decisão 22/10 | APROVADO / execução ponta a ponta NÃO AUDITADA |
| T02 | Força relativa comparável das 8 moedas G8, sem inferir força de cotação nominal isolada | Checkpoint e registro original | PARCIAL histórico / revalidar motor, dados e UI |
| T03 | Radar macro de 28 pares Forex, ranking TOP10 por qualidade/frescor/cenário | Registro 15/09; compromisso 23/09 | Radar base documentado; TOP10 completo NÃO HOMOLOGADO |
| T04 | Diferenciar radar de 28 pares e pipeline técnico completo dos 7 majors USD no baseline histórico | Registro original §7 | DISTINÇÃO OBRIGATÓRIA; situação atual precisa prova nova |
| T05 | CPI/Core CPI, PCE, NFP, AHE, desemprego, ADP, PPI, ISM/PMI, PIB e surpresas; calendário e recência | Histórico de decisões; Checkpoint §10 | APROVADO / cobertura live NÃO AUDITADA |
| T06 | Fed/FOMC/dot plot, BCE, BoE, BoJ, diferencial de juros e DXY, cruzamento entre macro e pares | Registro original; decisões | APROVADO / comprovação integrada PENDENTE |
| T07 | Geopolítica, eleições, eventos, lacunas de liquidez e cenários por ciclo | Decisão 08/10; radar eleições | DECISÃO CONVERSACIONAL A RECONCILIAR / NÃO AUDITADO |
| T08 | ICT/SMC: FVG, OB, BOS, Breaker, zonas e timing apenas após contexto macro | Checkpoint, registro, decisões | APROVADO / cobertura por par/timeframe NÃO AUDITADA |
| T09 | Wyckoff e VWAP sem confundir prioridade; Elliott fora do motor | Histórico 02/10: Wyckoff UNVERIFIED, Elliott descartado; decisões posteriores | CONFLITO/EVOLUÇÃO: confirmar prioridade de Wyckoff; não reativar Elliott |
| T10 | Backtests M15 até semanal, OOS, walk-forward, forward/shadow/paper, fricção, ranking auditável | Checkpoint e compromissos | PARCIAL / validação da escada e cobertura PENDENTE |
| T11 | Day/intra/swing/position com 2–3 setups simples no modo iniciante; avançado aprofundado | Decisões do produto | APROVADO / UX e conteúdo NÃO AUDITADOS |
| T12 | Gestão de risco, janela de notícias, dados ausentes/velhos → neutro/espera/bloqueio; score nunca probabilidade de lucro | Registro original + histórico | REGRA DE SEGURANÇA PRESERVADA; testes ponta a ponta PENDENTES |
| T13 | Trader cockpit compacto e ticker rolável, bandeiras corretas, hover/foco, mobile; evitar ticker em Negócios | Decisões 03/10 | ACEITE VISUAL ANTERIOR, regressão atual NÃO AUDITADA |
| T14 | Vídeos didáticos curtos FVG/OB/Breaker/PPR/Fibo 50/62/70.5/79; Centro de Treinamento | Decisões de conteúdo | APROVADO / produção e sincronismo NÃO AUDITADOS |
| T15 | Forex prioritário; WIN/WDO e índices/cripto em motores separados; sem misturar pesos/gates | Checkpoint 22/09; registro 15/09 | ARQUITETURA APROVADA / integração NÃO AUDITADA |
| T16 | Integração Trader ↔ Economia Global de Investimentos e comparação macro por país, visão BRL | Decisão 08/10 | DECISÃO CONVERSACIONAL A PERSISTIR / NÃO AUDITADO |
| T17 | AION como mentor de análises com memória, fontes, confiança calibrada e explicação do que invalidaria o viés | Decisões 22/10 + arquitetura AION | APROVADO / DEPENDE DA HOMOLOGAÇÃO DO NÚCLEO |

## Atenções que impedem conclusões precipitadas
- **Não confundir** “registrado no Checkpoint” com “implementado e funcionando”. A maior parte dos itens não recebeu inspeção de código/CI nesta tarefa documental.
- O registro original informa que, no estado histórico, **28 pares tinham radar macro e somente 7 pipeline completo**. Esse número pode ter evoluído; antes de atualizar o status, exigir teste, commit e execução recente.
- **Wyckoff:** a reconciliação de 29/09 marca prioridade não verificada. Decisão posterior menciona Wyckoff aprovado entre métodos. Registrar diferença temporal, verificar especificação atual e não implementar sem reconciliação expressa.
- **Economia Global** e **Radar de Eleições** são aprovações conversacionais posteriores aos checkpoints principais aqui inspecionados. Tratar como pendentes de incorporação no registro canônico, não como features concluídas.
- Pontos de mercado são probabilísticos: **direção macro ≠ entrada autorizada**. Comparar retornos e indicadores normalizados; não concluir que USD é “mais forte” apenas porque a cotação USD/JPY tem magnitude numérica maior que EUR/USD.
- A missão Cloud A183 prossegue em segurança. Não editar seus arquivos, criar integração operacional nem promover algo da cadeia Draft para main.

## Fases após seis P0 (sem antecipar ativação)
**G0 — Agora:** fechar P0 e realizar homologação adicional do núcleo; nenhuma execução crítica real.

**G1 — Auditoria de patrimônio:** mapa detalhado de arquivos e testes do Trader, checkpoint canônico atual, fontes de dados, custos, regressões, UX e verificações independentes. Reconciliar os itens T01–T17 sem prometer feature já feita.

**G2 — Produto mínimo pessoal:** painel “hoje / semana / mês”, força G8, ranking dos pares, eventos macro, explicação e invalidação; somente leitura, fontes documentadas, dados antigos → NO-DATA/ESPERA.

**G3 — Pesquisa técnica:** SMC/ICT, cenários validados, laboratório OOS/forward/shadow/paper; graduação progressiva, sem execução financeira autônoma.

**G4 — Ampliações:** Investimentos/Economia Global, WIN/WDO separados, Academy; Negócios supervisionado e escalável conforme demanda. AION comercial e recursos multimodais pagos **depois** de receita e orçamento.

## Próximos itens documentais verificáveis (sem envolver Cloud)
1. Encontrar o checkpoint canônico **mais recente** e seus manifestos/decisões após 02/10; comparar hashes/estados com este inventário. Não presumir que os quatro documentos analisados sejam toda a verdade atual.
2. Auditoria de diretórios e módulos Trader em `main`: mapear fonte, teste, runner, dados, limite/frescor e qualidade por requisito T01–T17. Registrar `IMPLEMENTADO` somente com prova.
3. Registrar como decisões canônicas as aprovações de 08/10 e 22/10, com revisão de conflitos e autorização sem sobrescrever entradas históricas.
4. Preparar roteiro de aceite do painel macro mínimo e orçamento, sem contratação de API.

**Estado final desta rodada:** reconciliação documental entregue; **nenhuma feature ou P0 homologado por este documento**. Sem merge, deploy, Worker nem despesa.


## Segunda rodada do pente-fino (22/10) — Complemento T18–T57
O inventário acima possui T01–T17 e **não era uma lista completa**. Após conferência adicional do backlog, documentos de produto, guias de backtest/TradingView, diretório `tradingview/`, contratos de pesquisa, módulos de runtime e issues #1080/#1160, a matriz foi ampliada com **40 requisitos/documentações complementares** em:

**[TRADER_PENTE_FINO_AMPLIADO_2026-10-22.md](TRADER_PENTE_FINO_AMPLIADO_2026-10-22.md)**.

Destaques antes omitidos:
- **T18 — Quarterly Theory:** decisão reconfirmada pelo proprietário; o Checkpoint de 22/09 só menciona `Quarterly/Weekly Profiles` na Academia. **Não equiparar à teoria completa implementada sem especificação e testes.**
- **T19 — Volume Profile:** aprovado como expansão condicional em `docs/product/PRODUCT_DECISIONS_2026-09-19.md`, com proibição de apresentar tick volume do Forex spot como volume global consolidado.
- **T20–T26 — TradingView/Pine:** guia de importação CSV e **cinco estratégias Pine reais** (BOS/CHOCH+OB, FVG, OTE, CRT, AMD/PO3), além de verificador de paridade *estática*; nenhum desses arquivos prova webhook/live ou execução idêntica no broker emulator.
- **T27–T31 — laboratório profundo:** comparador, walk-forward/OOS, parâmetros, spread/slippage, snapshots e replay.
- **T32–T39 — perfis e institucional:** perfil semanal estatístico, filtros de sessão/killzones, liquidez/SMT, PPR ainda indefinido, Wyckoff, VWAP, COT/Open Interest.
- **T40–T57 — cadeia funcional:** gráficos, briefing macro/voz, histórico/auditoria, eventos, Academy, corretoras e licenças, UX, mercados separados e segurança.

**Total de itens de rastreio nesta rodada: T01–T57.** É uma matriz de preservação de decisões; não é prova de que 57 funcionalidades estejam concluídas. A promessa de ausência absoluta de lacunas exigiria vasculhar todos os commits/chats/issues e reexecutar os testes; isso ainda não ocorreu. O material permanece isolado em PR Draft, sem merge, sem afetar Cloud A183, sem contratação, com HARD NO-GO e P0 0/6.
