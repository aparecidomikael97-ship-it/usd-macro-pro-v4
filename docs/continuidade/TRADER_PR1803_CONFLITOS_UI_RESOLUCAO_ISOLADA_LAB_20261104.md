# AtlasQuant Trader — integração isolada da PR #1803 com a interface compacta

Data: 04/11/2026. **Apenas LAB**, sem alterar `main`, PR #1803 ou o aplicativo publicado.

## Ponto de partida
- `main`: `4e69de16419860445596274db091c91aa9f08c2b`
- PR #1803: `e80eb1346421e171daf4f0b1a139c04ae2cec966`
- Simulação inicial: 3 conflitos de conteúdo nos arquivos
  `atlasquant_reference_ui.py`,
  `atlasquant_trader_radar_compact_ui.py`,
  `test_atlasquant_trader_radar_compact_ui.py`.

## Estratégia de reconciliação
- Preserva navegação compacta atual: **Início, Radar, Painel Mestre** (3 abas).
  O termo Scanner pode aparecer como informação de risco, **sem nova aba**.
- Preserva a **calculadora de abertura WIN**, a matriz de viés recolhível,
  o avatar e os dados de viés já previstos no caminho de interface atual.
- Preserva da PR #1803 o briefing macro, calendário, notícias,
  contexto oficial documental e checagem de disponibilidade dos dados.
- Encaminha as entradas `bias_evidence`, `news_data`,
  `official_data` e `calendar_data` conjuntamente, sem inferir
  valores ausentes.
- Mantém CSS responsivo de ambas as propostas e `notranslate` PT-BR.
- Aplica a janela mais rigorosa de **20 minutos** para leituras diárias
  na interface, recusando dados vencidos. Um resultado histórico BCE
  não é cotação negociável nem pode virar leitura em tempo real.

## Verificações executadas no AM12
- Integração por worktree isolada; nenhum commit sobre `main`.
- `python -m unittest -q` em 12 módulos relevantes:
  **168 testes aprovados** (incluindo o gate de 20 minutos; venv Python local com `tzdata`).
- `python -m pytest -q test_atlasquant_trader_bias_matrix.py`:
  **10 aprovados** (Python local com `pytest`).
- Os testes atualizados verificam ausência da rota de navegação
  `data-route="scanner"`, e não ausência da palavra Scanner em textos
  explicativos de auditoria.
- Suite remota CI da integração total: **ainda pendente**.

## Restrições
O conjunto da PR #1803 inclui muitos módulos e contratos de pesquisa.
Testes isolados **não** homologam toda a integração. Dados macro
declarados sem autenticação, ECB histórico não negociável, ausência de
preços independentes e validação OOS continuam bloqueios. Sem Worker,
Render, cron, ordens, despesas novas, merge ou deploy na `main`.

**Antes de qualquer integração definitiva:** verificar todos os testes de
qualidade e de UI, revisão humana dos arquivos alterados e autorização
expressa do proprietário.
