# Continuidade do AtlasQuant

## Como retomar

Leia este arquivo, o [registro original completo](docs/continuidade/REGISTRO_ORIGINAL_2026-09-15.md), o [plano de ativação](docs/continuidade/PLANO_ATIVACAO_RUNTIME.md) e o [histórico](HISTORICO_DE_ALTERACOES.md). O registro original preserva o conteúdo do Word entregue pelo usuário; não representa uma transcrição integral da conversa antiga.

Antes de alterar código, consulte as instruções AGENTS.md disponíveis, as SHAs das três branches e o workflow/log real mais recente. Se o estado mudou, informe a diferença. Não trate um resultado antigo de CI como resultado do commit atual.

## Regras acordadas

- Desenvolver em `atlasquant-dev`. Melhorias seguras em DEV estão autorizadas; “vamos lá” significa continuar a próxima etapa segura.
- Merge para `main`, promoção, alterações destrutivas de dados e mudanças de credenciais exigem autorização específica.
- Preservar o motor base, Safety Core fail-closed, rastreabilidade e dados ausentes como ausentes. Score não é probabilidade de lucro.
- Abertura da UI não deve gerar chamadas Twelve Data. Não inventar eventos, horários, entradas, stops, alvos ou estatísticas.
- Radar macro de 28 pares não equivale a pipeline técnico de 28 pares: o pipeline completo permanece nos 7 majors USD.
- Challenger e expansão 28FX não têm promoção automática. Academy/vídeos permanecem no plano após estabilização das telas; índices/WIN/WDO precisam de motores próprios.
- Ao concluir etapa importante, entregar arquivos e contexto cumulativo, com decisões, justificativas, pendências e testes realmente executados. Não prometer trabalho em background.

## Verificação desta retomada em 16/09/2026 UTC

Repositório: `aparecidomikael97-ship-it/usd-macro-pro-v4`.

| Referência | SHA consultada | Resultado |
| --- | --- | --- |
| DEV antes desta entrega documental | `d6d7779458dbd93735090d1eba45d44418fa672f` | Igual ao Word |
| main | `d5f6b4fe6c718ea3cb6bafd3758c31560523488a` | 7 commits após a main citada no Word |
| runtime | `2432a32833426f53cf834d2245ac3bf2ce10a5a1` | Igual ao Word |

[Quality tests 35047014369](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/35047014369): sucesso no SHA DEV acima. Log do job `104638929498`: `Ran 471 tests in 1.481s`, seguido de `OK`; etapa de compilação também concluída com sucesso. Esta retomada verificou a execução existente, não iniciou uma nova suíte.

Os 7 commits adicionais da main alteraram somente `dados/autopilot_inputs_v107.json`, `dados/autopilot_status_v107.json`, `dados/master_market_map_v102.json` e `dados/scanner_tecnico_v934.json`. Antes desta entrega documental, a comparação DEV/main era 191 à frente e 72 atrás. São valores de uma consulta, não constantes permanentes.

Os workflows consultados na main continuam apontando o histórico para `main`; os equivalentes na DEV apontam para `atlasquant-runtime`. A árvore runtime consultada ainda não contém `dados/atlasquant_flight_recorder.jsonl`, `dados/atlasquant_shadow_samples.jsonl` nem `dados/atlasquant_quota_shadow_v1.json`. A falta desses arquivos nessa branch não prova ausência de toda e qualquer amostra em outros locais.

## Etapa entregue

Registro original convertido para Markdown sem executar o código Python enviado anteriormente; contexto cumulativo; histórico; plano de ativação e rollback. Somente documentação foi alterada. Sem merge, mudança de modelo, workflow operacional, secrets ou dados.

## Próxima etapa segura no checkpoint anterior

Preparar em DEV uma ferramenta de inventário/reconciliação em modo somente leitura, com testes de dados inválidos, conflitos, duplicatas e mudança concorrente de SHA. Inventariar também budget/cache Twelve para impedir reinício indevido do consumo diário. A ferramenta deve gerar proposta e bloqueios sem fazer escrita remota.

Depois, revisar a proposta concreta de ativação com evidências e solicitar autorização específica somente para executar a promoção. Não há autorização de promoção nesta retomada.

## Validação ainda pendente

Ativação real do runtime, histórico persistente e evidência Shadow/Quota; validação técnica da pesquisa 28FX e inspeção de UX em produção. Os 471 testes não comprovam lucratividade nem substituem essas etapas. Critérios históricos: Shadow com 100 amostras totais e 10 por par, zero divergências críticas; Quota com pelo menos 20 rodadas de mercado aberto e critérios do módulo satisfeitos. Esses limiares permitem revisão manual, não ativação automática.

## Atualização da etapa de auditoria somente leitura

Implementados `atlasquant_migration_audit.py` e 9 testes em `test_atlasquant_migration_audit.py`, incluídos no Quality workflow. A ferramenta lê objetos Git locais de commits imutáveis e imprime JSON. Não acessa provedores, não faz fetch, não escreve no GitHub e não migra dados. Saída CLI: 0 sem pendências de inventário (não autoriza promoção); 2 com revisão pendente; 1 com falha de leitura.

Auditoria real registrada em `docs/continuidade/AUDITORIA_RUNTIME_2026-09-16.json`: main `1b5a07593838deba6561599ea4cc88183edbe016` versus runtime `2432a32833426f53cf834d2245ac3bf2ce10a5a1`. Nove arquivos rastreados em dados/: seis divergentes, três idênticos; sete itens exigem revisão, incluindo o cache diário mesmo idêntico. Migração e promoção automáticas permanecem desabilitadas.

Limitações explícitas: verifica sintaxe/estrutura genérica, hashes e algumas duplicatas, mas não valida schemas específicos, timestamps/frescor, IDs aninhados ou a reconciliação entre históricos. A estabilidade de refs é local; refs remotas devem ser reconsultadas antes de qualquer operação futura. Arquivos fora de dados/ não entram no inventário, portanto budget/cache externos ainda precisam ser mapeados.

Próxima etapa: mapear os caminhos efetivos de budget/cache e definir validadores de schema e reconciliação específicos dos seis arquivos divergentes. Não executar promoção nem gravar dados reais. Validação local desta etapa: 9 testes novos aprovados e compilação dos dois novos arquivos. Consultar o CI do commit desta implementação para o resultado da suíte completa; não reutilizar automaticamente os 471 testes da baseline antiga.


## 16/09/2026 UTC — checkpoint ICT/SMC estruturado + ZIP automático

Estado verificado após a auditoria/implementação desta etapa:

- \`atlasquant-dev\`: \`720beb2c43926ab7025268295bf6404502f1f292\` antes deste registro documental.
- \`atlasquant-runtime\`: \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`; permanece protegida e não foi alterada nesta etapa.
- \`main\`: \`b36ba5c457b446ea8b2dfd76f1157ba4af6c52d5\`; mudou fora desta etapa e não foi tocada.
- GitHub Actions Quality tests run \`35092388237\`: compile gate verde, **485 testes executados, 485 OK**.
- GitHub Actions checkpoint run \`35092388358\`: sucesso; artefato ZIP do snapshot DEV gerado.

### Nova camada ICT/SMC

Foi adicionado \`ict_structure_v111.py\`, sem chamadas de API e sem decidir direção macro.

Implementado de forma determinística/observacional:

- BOS de continuação por fechamento além de swing confirmado;
- CHOCH quando a quebra ocorre contra estrutura direcional anterior;
- estrutura mista é rotulada MSS em vez de forçar BOS/CHOCH;
- Order Block rule-based exige quebra estrutural recente + displacement relativo a ATR + candle oposto de origem;
- mitigação e invalidação da zona são rastreadas explicitamente.

Integração realizada em \`institutional_engine_v110.py\`, \`data_readiness_v1101.py\` e \`pair_intelligence_v110.py\`.

**Regra de segurança preservada:** BOS/CHOCH e Order Block aparecem no snapshot institucional/UI e respeitam frescor M15, mas ainda **não alteram os pesos do readiness institucional nem o Gate de execução**. Primeiro acumulamos validação; depois qualquer mudança de peso exige revisão.

Testes específicos adicionados em \`test_ict_structure_v111.py\` e integrados ao workflow de qualidade.

### Checkpoint ZIP

Foi criado \`.github/workflows/atlasquant-checkpoint.yml\` na DEV. Cada push em \`atlasquant-dev\` cria um ZIP do commit exato, incluindo \`CHECKPOINT_INFO.md\` e os arquivos de continuidade do repositório. O workflow não chama provedores e não altera a branch runtime.

Próximo passo seguro: ampliar os testes do novo motor (SELL, invalidação, dados insuficientes e regressões de integração) antes de considerar qualquer influência adicional no readiness/Gate.


## 16/09/2026 UTC — hardening BOS/CHOCH/Order Block

- DEV testada em \`04276854213c3b75534099d92e0a6dfc1a5140e8\`.
- Quality run \`35092846046\`: compile gate verde, **491 testes executados, 491 OK**.
- Adicionados testes SELL para BOS e CHOCH.
- Adicionado teste de invalidação fail-closed de Order Block.
- Adicionado teste de dados insuficientes: estrutura/Order Block não podem alegar confirmação.
- Adicionados testes de integração do Data Readiness: \`structure\` e \`order_block\` são mascarados quando M15 está stale/insuficiente e voltam a aparecer quando M15 está fresco.
- Nenhuma alteração de pesos/readiness/Gate nesta etapa.
- Checkpoint ZIP automático da DEV foi gerado com sucesso pelo run \`35092846140\`.

Próximo passo seguro: auditar a qualidade semântica do detector em cenários de mercado lateral/flat, equal highs/lows e múltiplas quebras próximas; só depois discutir qualquer peso no Gate.


## 16/09/2026 UTC — robustez contra lateralização e ruído estrutural

- DEV validada em \`cd92cb5f4bbdbc7c6c1d10f5cc561e9d6fcd5714\`.
- Quality run \`35093251163\`: compile gate verde, **495 testes executados, 495 OK**.
- \`ict_structure_v111.py\` atualizado para V1.1.2.
- Adicionada tolerância baseada em ATR para evitar classificar microdiferenças/equal-ish highs/lows como estrutura direcional forte.
- Fechamentos marginais dentro da tolerância de ruído não geram BOS/CHOCH.
- Um mesmo swing confirmado pode gerar no máximo um evento estrutural; retestes/recruzamentos do mesmo nível não criam BOS/CHOCH duplicados.
- Metadados \`break_margin\` e \`noise_tolerance\` foram adicionados à leitura para auditoria.
- Testes adversariais adicionados para range lateral, pivôs quase iguais, reutilização do mesmo swing e rompimento marginal.
- Pesos do readiness institucional e Gate permanecem inalterados.
- Checkpoint ZIP automático foi gerado no run \`35093251055\`.
- Runtime continua em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main foi observada em \`8a41a9acc8360753bbb31627e227156182fdac2b\`; essa mudança ocorreu fora desta etapa e não foi tocada.

Próximo passo seguro: revisar a seleção/qualidade do Order Block em cenários com múltiplos candles de origem e confirmar que a zona escolhida não reaproveita origem velha depois de uma nova quebra estrutural.


## 16/09/2026 UTC — Order Block vinculado à perna estrutural mais recente

Estado verificado:

- DEV testada em \`cae59a537d9d0f39f39036c0443b3469a54eb5a1\`.
- Quality run \`35093708480\`: compile gate verde, **499 testes executados, 499 OK**.
- Runtime permanece em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main observada em \`8a41a9acc8360753bbb31627e227156182fdac2b\`; nenhuma alteração foi feita nela.

### Mudanças no ICT Structure Engine V1.1.3

- Order Block agora considera o **evento estrutural mais recente**, não apenas a última quebra alinhada antiga.
- Se a quebra mais recente estiver contra o lado macro, o motor entra em fail-closed: \`ESTRUTURA MAIS RECENTE CONTRÁRIA — SEM ORDER BLOCK\`.
- A busca pelo candle de origem fica limitada à **perna estrutural atual**:
  - não atravessa o swing de referência;
  - não atravessa o evento estrutural anterior;
  - mantém limite máximo de busca de 8 candles antes da quebra.
- Entre múltiplos candles opostos válidos na perna atual, escolhe o mais recente, imediatamente anterior ao displacement.
- Foram adicionados índices auditáveis: \`structure_index\`, \`reference_pivot_index\`, \`origin_search_start\`, \`origin_index\`.

### Evidência de teste

Novos testes cobrem:

- quebra contrária mais nova bloqueando Order Block antigo;
- proibição de reutilizar candle de origem anterior à perna atual;
- seleção do candle oposto mais recente entre múltiplos candidatos;
- nova quebra no mesmo lado assumindo sua própria zona/origem.

O primeiro run desta etapa (\`35093608004\`) encontrou 1 regressão no teste antigo de invalidação: o novo bloqueio de estrutura contrária, corretamente mais conservador, passou a ocorrer antes da invalidação da zona. O teste foi corrigido para isolar especificamente a invalidação do Order Block, sem remover o novo bloqueio fail-closed. O run seguinte ficou totalmente verde.

**Regra preservada:** BOS/CHOCH e Order Block continuam observacionais. Nenhum peso de readiness institucional nem Gate foi alterado.

Próximo passo seguro: testar Order Block SELL com múltiplas origens e cenários de mitigação parcial/reteste, mantendo a lógica fail-closed antes de qualquer discussão sobre pesos.


## 16/09/2026 UTC — Order Block SELL, mitigação parcial e retestes

Estado verificado:

- DEV testada em \`66d6257991aabcd6114a6171c98de98ab2e34755\`.
- Quality run \`35094192679\`: compile gate verde, **503 testes executados, 503 OK**.
- Runtime permanece em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main permanece em \`8a41a9acc8360753bbb31627e227156182fdac2b\`; nenhuma alteração foi feita nela.

### ICT Structure Engine V1.1.4

- Adicionada telemetria de mitigação do Order Block:
  - \`mitigation_depth_pct\`;
  - \`retest_count\`;
  - \`first_touch_time\`.
- Mitigação parcial (<50%) recebe estado próprio: \`ORDER BLOCK PARCIALMENTE MITIGADO / ATIVO\`.
- Retestes separados são contados por episódios, não apenas por número de candles dentro da zona.
- Wick que atravessa a zona sem fechamento além da borda de invalidação não invalida automaticamente o OB.
- SELL ganhou cobertura simétrica para:
  - múltiplas origens bullish;
  - escolha da origem mais recente;
  - mitigação parcial;
  - múltiplos retestes;
  - wick-through sem fechamento invalidante.

### Defeito encontrado e corrigido pelos testes

O primeiro run desta etapa (\`35094093071\`) encontrou 2 falhas. A métrica inicial de profundidade usava o maior valor entre penetração por cima e por baixo, o que superestimava a mitigação em SELL. A função foi corrigida para medir a profundidade pela borda correta do Order Block:

- BUY: entrada/mitigação medida a partir da borda superior;
- SELL: entrada/mitigação medida a partir da borda inferior.

Após a correção, o run \`35094192679\` passou com **503/503**.

**Regra preservada:** essa telemetria é observacional e não altera Gate, pesos de readiness ou autorização de execução.

Próximo passo seguro: testar a mesma telemetria de profundidade/reteste no lado BUY e validar cenários de gap/vela que toca a zona apenas por wick, mantendo simetria entre os dois lados.


## 16/09/2026 UTC — backtest operacional + TradingView CSV + ledger

Estado verificado:

- DEV testada em \`f7adc098249c09c3d544786a2f8a110bf5602d6b\`.
- Quality run \`35095699342\`: compile gate verde, **518 testes executados, 518 OK**.
- Runtime não foi alterado nesta etapa.

### Novo motor

Foi criado \`atlasquant_operational_backtest.py\`:

- recebe candles OHLC e planos com entrada/stop/alvo explícitos;
- não inventa níveis;
- inicia a simulação após o candle do sinal por padrão (anti-look-ahead);
- plano inválido falha fechado como \`NO_TRADE\`;
- stop + alvo no mesmo candle é tratado como LOSS por ambiguidade intrabar;
- calcula Gain/Loss/BE, resultado líquido em R, MFE/MAE, drawdown,
  profit factor e sequências;
- permite agrupamento por setup, sessão e outras dimensões;
- produz ledger tabular completo.

### Nova tela de Backtest

Foi criado \`atlasquant_backtest_panel.py\` e integrado à aba Backtest:

- upload de candles CSV exportados do TradingView;
- upload da planilha de sinais;
- aliases de colunas em inglês/português;
- download de modelos vazios;
- configuração de janela para entrada, tempo máximo em posição e custos em R;
- métricas gerais, por operacional/setup e por sessão;
- download do ledger completo em CSV.

O backtest legado foi mantido por compatibilidade, abaixo do novo painel.

Guia operacional: \`docs/backtest/GUIA_TRADINGVIEW_BACKTEST.md\`.

Próximo passo seguro: construir a ponte Pine Script apenas para os operacionais
que possam ser reproduzidos de forma determinística no TradingView, sem fingir
que o Pine consegue consumir diretamente o contexto macro do AtlasQuant.


## 16/09/2026 UTC — Pine Strategy + replay automático sem planilha de sinais

Estado verificado:

- DEV testada em \`2cb38cca9a2958a77945f9ca2b3eb00aae926ae8\`.
- Quality run \`35097346652\`: compile gate verde, **530 testes executados, 530 OK**.
- Runtime permanece em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main observada em \`107c77100bc49c39da922a3bfb18ff7557d74d22\`; nenhuma alteração foi feita nela.

### Ponte TradingView

Foi criado \`tradingview/atlasquant_bos_choch_ob_strategy_v1.pine\`:

- Strategy Tester, não indicador apenas visual;
- pivôs confirmados;
- BOS/CHOCH por fechamento além de swing confirmado;
- tolerância de ruído por ATR;
- evita reutilizar o mesmo swing;
- Order Block baseado na origem oposta mais recente dentro da perna estrutural;
- exige displacement mínimo;
- entrada midpoint/proximal;
- stop com buffer ATR;
- alvo configurável em R;
- filtro de sessão e lado;
- sem \`request.security\` e sem primitivas conhecidas de lookahead;
- \`process_orders_on_close=false\`, preservando processamento de ordens no próximo candle.

O painel Backtest oferece download direto do Pine.

### Replay automático Python

Foi criado \`atlasquant_strategy_replay.py\` e integrado à aba Backtest:

- usuário pode enviar apenas o CSV de candles;
- o AtlasQuant percorre o histórico candle a candle;
- gera sinais BOS/CHOCH + Order Block apenas quando o evento confirmado ocorre no candle atual do replay;
- deriva entrada/stop/alvo por regras fixas de pesquisa;
- roda o backtest sem reutilizar informação futura;
- bloqueia sobreposição de posição no mesmo par com \`single_position_per_pair=True\`;
- exporta os sinais gerados e o ledger final em CSV;
- mantém resultado separado por setup e sessão.

O replay usa janela estrutural limitada para evitar crescimento quadrático em CSVs longos.

**Limite mantido:** Pine/replay são pesquisa técnica. Macro, Fed, eventos, força relativa, Safety Core e Gate continuam no motor AtlasQuant e não são fingidos no TradingView.

Próximo passo seguro: ampliar a validação de paridade entre Pine e replay Python e adicionar FVG como segundo operacional técnico objetivo, sem misturar estatísticas entre estratégias.


## 16/09/2026 UTC — FVG como segundo operacional independente

Estado verificado:

- DEV testada em \`34e7bc55247fd4e43412a91853bff1ee39114a52\`.
- Quality run \`35097997003\`: compile gate verde, **540 testes executados, 540 OK**.
- Runtime permanece em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main permanece em \`107c77100bc49c39da922a3bfb18ff7557d74d22\`; nenhuma alteração foi feita nela.

### Replay FVG Python

Foi criado \`atlasquant_fvg_replay.py\`:

- FVG BUY: low do terceiro candle acima do high de dois candles atrás;
- FVG SELL: high do terceiro candle abaixo do low de dois candles atrás;
- sinal é criado somente no candle em que o gap nasce;
- entrada Midpoint ou Proximal;
- stop na borda oposta, com buffer ATR opcional;
- alvo em múltiplos de R;
- filtro opcional de tamanho mínimo do gap em ATR;
- BUY e SELL podem ser ativados separadamente;
- cada sinal registra tamanho do gap, gap/ATR, zona, sessão e índice histórico;
- usa o mesmo motor genérico de backtest e bloqueio de posição sobreposta por par.

### Pine Strategy FVG

Foi criado \`tradingview/atlasquant_fvg_strategy_v1.pine\`:

- Strategy Tester independente do BOS/CHOCH + OB;
- FVG bullish/bearish de três candles;
- entrada Midpoint/Proximal;
- stop/buffer ATR;
- alvo em R;
- validade do setup em candles;
- filtro de sessão e lado;
- \`process_orders_on_close=false\`;
- sem \`request.security\` e sem primitivas conhecidas de lookahead.

O workflow de qualidade agora também dispara quando arquivos em \`tradingview/**\` mudam.

### UI / estatística separada

A aba Backtest ganhou um segundo bloco automático exclusivo para FVG. Ele não mistura
estatísticas com BOS/CHOCH + Order Block. O usuário pode baixar o Pine FVG, os sinais
gerados e o ledger completo separadamente.

O primeiro run desta etapa (\`35097878643\`) encontrou 1 falha apenas no contrato textual
de segurança: o comentário do Pine continha literalmente o nome de uma primitiva
proibida. O comentário foi corrigido sem mudar a lógica; o run seguinte
(\`35097997003\`) ficou totalmente verde com 540/540.

**Regra preservada:** FVG continua pesquisa técnica. Não altera pesos do ICT readiness,
Safety Core, Gate ou Runtime.

Próximo passo seguro: criar validação de paridade de regras entre Pine e replay Python
para FVG e BOS/CHOCH+OB, e depois avançar para OTE como terceiro operacional objetivo.
