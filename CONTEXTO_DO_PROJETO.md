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


## 16/09/2026 UTC — contrato de paridade TradingView ↔ Python

Estado verificado:

- DEV testada em \`5c09c5a62802c0b7b071da02d1be29d7e118c52e\`.
- Quality run \`35098491162\`: compile gate verde, **543 testes executados, 543 OK**.
- Runtime permanece em \`7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1\`.
- Main permanece em \`107c77100bc49c39da922a3bfb18ff7557d74d22\`; nenhuma alteração foi feita nela.

### Validador de drift Pine/Python

Foi criado \`atlasquant_tradingview_parity.py\`, offline/read-only, para impedir drift silencioso
entre as estratégias Pine e os replays Python.

O contrato verifica:

- processamento das ordens após o candle do sinal;
- ausência de série externa no Pine;
- defaults de RR, stop buffer e modo de entrada;
- FVG: fórmula bullish/bearish, gap mínimo e validade padrão da ordem;
- BOS/CHOCH + OB: warmup, pivôs 2/2, ATR 14, ruído 0,05 ATR, origem limitada a 8 candles,
  displacement 0,65 body/ATR e 0,85 range/ATR;
- validade padrão da ordem pendente alinhada em 8 candles entre Pine e backtest Python.

A Pine BOS/CHOCH + OB foi ajustada para:

- \`maxSetupAge = 8\`, alinhando a janela padrão de entrada com o Python;
- warmup explícito de 20 candles (\`bar_index >= 19\`), alinhando o início do replay técnico.

A aba Backtest ganhou um painel **Paridade TradingView ↔ Python** com o status das
verificações.

### Limite explícito

Esse contrato é **paridade estática de regras**, não compilação do Pine e não prova
equivalência integral com o broker emulator do TradingView. Timezone, sessão configurada
manualmente e arredondamento por tick continuam podendo causar diferenças práticas.

Próximo passo seguro: OTE como terceiro operacional independente, mantendo replay Python,
Pine Strategy, estatísticas e ledger separados antes de qualquer combinação de confluência.


## 16/09/2026 UTC — OTE como terceiro operacional independente

Estado verificado:

- DEV testada em `adfe95b15386fb8333aadfd4cea8df43e8dcbe24`.
- Quality run `35099427531`: compile gate verde, **552 testes executados, 552 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main observada em `d66df22927f36190caa0b8f6b012e7b9ba921cd5`; nenhuma alteração foi feita nela.

### Replay OTE Python

Foi criado `atlasquant_ote_replay.py`:

- operacional OTE 62%-79% independente;
- usa geometria de impulso alinhada ao ICT Engine: lookback 28 e extremo recente 12;
- BUY: ancora low anterior -> high recente;
- SELL: ancora high anterior -> low recente;
- sinaliza no primeiro fechamento dentro da zona OTE por impulso;
- evita sinal repetido no mesmo impulso;
- se BUY e SELL estiverem válidos no mesmo candle, escolhe de forma determinística o candidato mais próximo do sweet spot 70,5%;
- entrada `SWEET_705` ou midpoint da zona;
- stop no swing de origem com buffer ATR opcional;
- alvo configurável em R;
- filtro opcional de impulso mínimo em ATR;
- exporta retração, zona OTE, sweet 70,5%, swings, índices e impulso/ATR.

### Pine Strategy OTE

Foi criado `tradingview/atlasquant_ote_strategy_v1.pine`:

- Strategy Tester separado de BOS/CHOCH+OB e FVG;
- OTE 62%-79%;
- lookback 28 / extremo recente 12;
- sweet spot 70,5%;
- entrada Sweet 70.5 ou Zone midpoint;
- stop buffer ATR e alvo em R;
- filtro de impulso/ATR, lado e sessão;
- validade padrão de ordem pendente em 8 candles;
- `process_orders_on_close=false`;
- sem série externa e sem primitivas conhecidas de lookahead.

### UI e paridade

A aba Backtest agora possui terceiro bloco automático exclusivo para OTE, com Pine próprio,
sinais exportáveis e ledger separado.

O contrato `atlasquant_tradingview_parity.py` foi ampliado para OTE e compara defaults e
regras centrais entre Pine e Python: RR, stop buffer, lookback, janela recente, filtro de
impulso, 62/70,5/79, warmup e validade da ordem.

**Regra preservada:** OTE continua pesquisa técnica independente. Não altera Gate, Safety Core,
pesos do ICT readiness, Runtime ou macro/Fed.

Próximo passo seguro: endurecer o OTE contra reancoragem prematura de swings e validar cenários
de dois impulsos próximos, depois avançar para CRT/AMD apenas se as regras puderem ser
reproduzidas de forma objetiva e auditável.


## 16/09/2026 UTC — hardening OTE contra reancoragem prematura

Estado verificado:

- DEV testada em `2ca4e249a3dbd7e0629ffe8f3f602aa1f2668c8b`.
- Quality run `35101330822`: compile gate verde, **554 testes executados, 554 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main observada em `d66df22927f36190caa0b8f6b012e7b9ba921cd5`; nenhuma alteração foi feita nela.

### Re-anchor guard OTE

O replay OTE deixou de aceitar extensões marginais do mesmo impulso como se fossem um novo setup:

- após um OTE BUY emitido, o próximo BUY só pode nascer de um swing low de origem **posterior** ao terminal high do impulso anterior;
- após um OTE SELL emitido, o próximo SELL só pode nascer de um swing high de origem **posterior** ao terminal low do impulso anterior;
- novos highs/lows que apenas estendem a mesma perna não geram um segundo OTE;
- um segundo impulso próximo continua permitido quando sua origem realmente começa depois do terminal anterior.

Foram adicionados metadados auditáveis aos sinais OTE:

- `impulse_origin_index`;
- `impulse_terminal_index`;
- `previous_same_side_terminal_index`;
- `reanchor_guard=NEW_ORIGIN_AFTER_PREVIOUS_TERMINAL`.

A Pine OTE recebeu a mesma regra, e o contrato TradingView ↔ Python passou a verificar
explicitamente o re-anchor guard nos dois lados.

Novos testes cobrem:

- mesma origem + novo extremo => não cria segundo sinal;
- novo impulso com origem após o terminal anterior => pode criar novo sinal.

**Regra preservada:** OTE continua pesquisa técnica e não altera Gate, Safety Core, pesos,
Runtime ou decisões macro/Fed.

Próximo passo seguro: iniciar CRT como quarto operacional somente com definição objetiva de
range/sweep/reclaim e manter estatística totalmente separada; AMD/Power of Three vem depois,
por exigir mais estados e validação temporal.


## 16/09/2026 UTC — CRT como quarto operacional independente

Estado verificado:

- DEV testada em `9705c7b8d04c4df3269b2bc54a219bf442edab92`.
- Quality run `35101892468`: compile gate verde, **564 testes executados, 564 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main observada em `ad2763827bcdd0822efad7f04a0286a5a91cd8af`; mudou fora desta etapa e não foi alterada.

### Replay CRT Python

Foi criado `atlasquant_crt_replay.py`, separado dos demais operacionais.

Regra técnica objetiva, alinhada ao detector CRT já existente:

- candle 1 = anchor range;
- BUY: candle 2 varre abaixo do anchor low e fecha de volta acima; candle 3 fecha acima do candle 2 e acima do midpoint;
- SELL: candle 2 varre acima do anchor high e fecha de volta abaixo; candle 3 fecha abaixo do candle 2 e abaixo do midpoint;
- entrada de pesquisa = fechamento do candle de delivery;
- stop = extremo da varredura/anchor, com buffer ATR opcional;
- alvo estrutural = lado oposto do anchor range;
- filtro opcional de RR mínimo;
- execução continua começando somente após o candle do sinal.

### Pine Strategy CRT

Foi criado `tradingview/atlasquant_crt_strategy_v1.pine`:

- Strategy Tester independente;
- regras BUY/SELL de raid/reclaim + delivery;
- stop buffer ATR;
- RR mínimo;
- validade padrão da ordem pendente em 8 candles;
- filtros de lado e sessão;
- `process_orders_on_close=false`;
- sem série externa e sem primitivas conhecidas de lookahead.

### UI / paridade / testes

A aba Backtest agora possui quarto bloco automático exclusivo para CRT, Pine próprio, sinais
exportáveis e ledger separado.

O contrato TradingView ↔ Python foi ampliado para verificar defaults e fórmulas centrais do CRT:
stop buffer, RR mínimo, warmup, raid/reclaim BUY/SELL, delivery BUY/SELL, entrada no delivery close
e alvos nas bordas opostas do anchor.

Novos testes cobrem BUY, SELL, raid sem reclaim, delivery sem confirmação, filtro RR, parâmetros
inválidos e integração com o backtester genérico.

**Regra preservada:** CRT continua pesquisa técnica independente e não altera Gate, Safety Core,
pesos, Runtime ou contexto macro/Fed.

Próximo passo seguro: AMD/Power of Three em modo de pesquisa separado, começando por uma máquina
de estados Accumulation → Manipulation → Distribution com testes de sequência temporal antes de
qualquer Pine ou influência no Gate.


## 16/09/2026 UTC — AMD / Power of Three como quinto operacional independente

Estado verificado:

- DEV testada em `06d70dfad51fe310fcce5497ff366534aa56f21c`.
- Quality run `35102692080`: compile gate verde, **576 testes executados, 576 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main permanece em `ad2763827bcdd0822efad7f04a0286a5a91cd8af`; não foi alterada nesta etapa.

### Replay AMD / Power of Three

Foi criado `atlasquant_amd_replay.py` com máquina de estados temporal estrita:

1. **Accumulation** — range congelado em candles anteriores;
2. **Manipulation** — sweep + reclaim do range congelado;
3. **Distribution** — somente em candle posterior à manipulação.

Regras:

- BUY: sweep abaixo do `acc_low` + fechamento de volta acima; distribuição posterior fecha acima do midpoint e acima do fechamento da manipulação;
- SELL: espelho exato acima do `acc_high`;
- o candle de manipulação não pode confirmar distribuição no mesmo candle;
- manipulação expira após janela configurável;
- entrada de pesquisa = fechamento da distribuição;
- stop = extremo da manipulação com buffer ATR opcional;
- alvo estrutural = borda oposta do range de acumulação;
- filtro de RR mínimo;
- se um candle varrer os dois lados, apenas uma manipulação é mantida: o sweep de maior profundidade normalizada vence; empate favorece BUY de forma determinística;
- resultado segue separado dos demais operacionais.

### Pine Strategy AMD

Foi criado `tradingview/atlasquant_amd_strategy_v1.pine`:

- Strategy Tester independente;
- máquina de estados temporal;
- acumulação padrão 8 candles;
- distribuição deve ocorrer depois da manipulação;
- janela padrão até distribuição = 4 candles;
- stop buffer ATR e RR mínimo;
- filtros de lado e sessão;
- validade da ordem pendente em 8 candles;
- `process_orders_on_close=false`;
- sem série externa e sem primitivas conhecidas de lookahead.

### UI / paridade / testes

A aba Backtest agora possui quinto bloco automático exclusivo para AMD/PO3, Pine próprio,
sinais exportáveis e ledger separado.

O contrato TradingView ↔ Python foi ampliado para validar:

- accumulation bars;
- distribution window;
- stop buffer e RR mínimo;
- warmup;
- manipulation BUY/SELL;
- distribution posterior BUY/SELL;
- proibição de distribuição no candle da manipulação;
- resolução determinística de sweep nos dois lados;
- alvos estruturais nas bordas da acumulação.

O primeiro run desta etapa (`35102616879`) encontrou 1 falha em um teste que chamava de
"distribuição válida" um candle que ainda não fechava acima do fechamento da manipulação BUY.
O teste foi corrigido para respeitar a regra mais conservadora, sem afrouxar o motor.
O run seguinte (`35102692080`) ficou verde com **576/576**.

**Regra preservada:** AMD/PO3 continua pesquisa técnica independente. Não altera Gate,
Safety Core, pesos de readiness, Runtime ou decisões macro/Fed.

Próximo passo seguro: consolidar um comparador de performance entre os cinco operacionais
(BOS/CHOCH+OB, FVG, OTE, CRT, AMD) sem misturar seus sinais, para descobrir objetivamente
quais regras têm melhor expectativa, drawdown e estabilidade por par/sessão.


## 16/09/2026 UTC — comparador de performance dos 5 operacionais

Estado verificado:

- DEV testada em `92d1cf49012ad5400f5d6a3eb1af8e80fe36057a`.
- Quality run `35103238881`: compile gate verde, **582 testes executados, 582 OK**.
- Runtime permanece protegida e não foi alterada nesta etapa.
- Main não foi alterada nesta etapa.

### Comparador de pesquisa

Foi criado `atlasquant_strategy_comparator.py` para executar e comparar, no mesmo CSV OHLC,
os cinco operacionais técnicos independentes:

1. BOS/CHOCH + Order Block;
2. FVG;
3. OTE 62–79%;
4. CRT;
5. AMD / Power of Three.

O comparador preserva a identidade de cada estratégia e **não mistura sinais**.

Para cada operacional, registra separadamente:

- signals;
- trades executados;
- gains/losses/breakeven/no-trade;
- win rate observado;
- expectativa em R;
- resultado líquido em R;
- profit factor;
- drawdown máximo em R;
- maior sequência de loss;
- casos OHLC ambíguos;
- relação net R / drawdown;
- faixa de tamanho da amostra.

### Proteção contra leitura enganosa de amostra pequena

O comparador possui um limiar configurável para ranking observado, padrão de **20 trades**.

- abaixo do limiar, o operacional continua com todas as métricas visíveis;
- porém não recebe posição no ranking de expectativa observada;
- o ranking é explicitamente histórico/descritivo e não vira probabilidade, recomendação,
  score de lucro ou autorização de Gate.

Faixas descritivas:

- <20 trades: `AMOSTRA PEQUENA`;
- 20–49: `AMOSTRA INICIAL`;
- 50–99: `AMOSTRA INTERMEDIÁRIA`;
- >=100: `AMOSTRA MAIOR`.

### UI e exportação

A aba Backtest ganhou o bloco **Comparador dos 5 operacionais**.

Com um único CSV, o usuário pode:

- rodar os 5 replays com defaults de pesquisa;
- comparar resultados gerais;
- comparar por sessão;
- exportar tabela de comparação;
- exportar ledger combinado, mantendo `strategy_family` e `operacional` em cada linha.

**Regra preservada:** comparador é pesquisa histórica. Não altera Gate, Safety Core,
readiness, Runtime ou direção macro/Fed.

Próximo passo seguro: adicionar análise de estabilidade temporal (janelas/blocos do histórico)
para detectar se um setup só parece bom em um trecho específico, antes de qualquer tentativa
de usar performance histórica como filtro operacional.


## 16/09/2026 UTC — estabilidade temporal dos 5 operacionais

Estado verificado:

- DEV testada em `ee21ff8abb1236d241ad6da8a71e654f49fc0f52`.
- Quality run `35103716697`: compile gate verde, **588 testes executados, 588 OK**.
- Runtime permanece protegida e não foi alterada nesta etapa.
- Main não foi alterada nesta etapa.

### Diagnóstico de estabilidade temporal

Foi criado `atlasquant_strategy_stability.py` para testar se a performance observada de cada
operacional permanece parecida ao longo do histórico ou se está concentrada em apenas um trecho.

O diagnóstico:

- usa somente trades executados com timestamp válido;
- preserva cada estratégia separadamente;
- divide cronologicamente os trades de cada operacional em blocos de tamanho quase igual;
- suporta 3, 4 ou 5 blocos;
- calcula por bloco:
  - trades;
  - gains/losses/BE;
  - win rate observado;
  - expectativa em R;
  - net R;
  - drawdown máximo;
  - maior sequência de loss.

### Status temporal descritivo

Cada operacional recebe apenas um status histórico:

- `POSITIVE_ACROSS_FOLDS`: expectativa positiva em todos os blocos;
- `NEGATIVE_ACROSS_FOLDS`: expectativa negativa em todos os blocos;
- `MIXED_ACROSS_FOLDS`: sinais diferentes entre os blocos;
- `INSUFFICIENT`: amostra mínima por bloco não atendida.

Também são mostrados:

- número de blocos positivos/negativos/neutros;
- percentual de blocos positivos;
- pior e melhor expectativa por bloco;
- spread entre melhor/pior expectativa;
- desvio da expectativa;
- net R total.

A amostra mínima por bloco é configurável na tela, padrão **5 trades**.

### UI / exportação

O bloco **Comparador dos 5 operacionais** agora possui:

- seletor de 3/4/5 blocos temporais;
- mínimo de trades por bloco;
- tabela de estabilidade temporal;
- detalhamento de cada bloco;
- exportação CSV dos blocos temporais.

Esse diagnóstico não cria probabilidade, previsão, score de lucro, recomendação nem autorização
de Gate. Ele serve apenas para mostrar quando um resultado histórico depende de uma fase
específica da amostra.

Próximo passo seguro: adicionar validação por janela móvel / walk-forward simples e medir
degradação entre treino e teste sem otimização automática, mantendo tudo como pesquisa.


## 16/09/2026 UTC — walk-forward dos 5 operacionais

Estado verificado:

- DEV testada em `76a79c6760e6e5b76b4156cb3bab989fbd7dafa1`.
- Quality run `35104652826`: compile gate verde, **595 testes executados, 595 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main observada em `07b632a28e82a8cdb83f7a5219fc73d6ceb2f42a`; mudou fora desta etapa e não foi alterada.

### Diagnóstico walk-forward

Foi criado `atlasquant_strategy_walkforward.py`.

O método usa apenas os trades históricos já executados pelos cinco replays e cria janelas
cronológicas de **treino expansivo → teste posterior**, sem otimização automática de parâmetros.

Configuração padrão:

- 60% inicial do histórico como treino;
- 3 janelas OOS posteriores;
- mínimo de 20 trades no treino;
- mínimo de 5 trades em cada janela de teste.

Também podem ser usados:

- treino inicial de 50%, 60% ou 70%;
- 2, 3 ou 4 janelas OOS.

Em cada janela:

- o treino contém somente trades anteriores ao período de teste;
- o teste nunca volta para dados anteriores;
- depois de cada teste, a janela de treino se expande cronologicamente;
- parâmetros e regras dos operacionais permanecem fixos;
- nenhum resultado do teste é usado para recalibrar o setup.

### Métricas walk-forward

Por janela são registrados:

- número de trades no treino e no teste;
- expectativa em R no treino;
- expectativa em R no teste;
- diferença `test expectancy - train expectancy`;
- net R de treino e teste;
- win rate de treino e teste;
- drawdown e maior sequência de loss no teste.

Resumo descritivo por operacional:

- `POSITIVE_ALL_OOS_WINDOWS`;
- `NEGATIVE_ALL_OOS_WINDOWS`;
- `MIXED_OOS_WINDOWS`;
- `INSUFFICIENT`.

Também mostra:

- número de janelas OOS positivas/negativas;
- percentual de janelas positivas;
- expectativa média de treino;
- expectativa média OOS;
- degradação média da expectativa;
- pior e melhor expectativa OOS;
- net R total OOS.

### UI / exportação

O **Comparador dos 5 operacionais** ganhou:

- seletor de percentual inicial de treino;
- número de janelas OOS;
- mínimos de trades no treino/teste;
- resumo walk-forward;
- tabela detalhada das janelas;
- exportação `atlasquant_walkforward_5_*.csv`.

**Limite preservado:** walk-forward é diagnóstico histórico fora da amostra, não previsão,
não probabilidade de lucro, não otimiza parâmetros e não altera Gate, Safety Core,
readiness, Runtime ou macro/Fed.

Próximo passo seguro: auditar custos/slippage e sensibilidade dos resultados a custos antes de
considerar qualquer uso dos resultados históricos como evidência operacional.


## 16/09/2026 UTC — sensibilidade a custos e slippage

Estado verificado:

- DEV testada em `cdeff107162dd609d487a74bb0545e3c677a14f1`.
- Quality run `35105537324`: compile gate verde, **605 testes executados, 605 OK**.
- Runtime permanece protegida e não foi alterada nesta etapa.
- Main não foi alterada por esta etapa.

### Slippage explícito no motor de backtest

O motor `atlasquant_operational_backtest.py` agora aceita separadamente:

- `cost_r`;
- `slippage_r`;
- `total_friction_r = cost_r + slippage_r`.

A fricção é aplicada de forma conservadora ao resultado bruto em R de cada trade executado:

`net_r = gross_r - cost_r - slippage_r`.

Custos/slippage negativos, não finitos ou inválidos falham fechado com
`INVALID_FRICTION`.

O ledger passou a registrar `cost_r`, `slippage_r` e `total_friction_r`.

**Limite explícito:** `slippage_r` é um drag adverso fixo em R por trade para stress histórico.
Não é simulador tick a tick e não altera retroativamente a sequência OHLC de entrada/stop/alvo.

### Diagnóstico de sensibilidade

Foi criado `atlasquant_strategy_friction.py`.

O diagnóstico reprecifica **os mesmos trades já executados** em diferentes cenários de atrito.
Ele não regenera sinais nem muda entrada, stop, alvo ou tempo de saída entre os cenários.

Por estratégia/cenário registra:

- custo em R;
- slippage em R;
- fricção total em R;
- trades;
- gain/loss/BE;
- win rate observado;
- expectativa em R;
- net R;
- profit factor;
- drawdown;
- maior sequência de loss;
- sinal da expectativa após fricção.

Resumo descritivo:

- `POSITIVE_ALL_TESTED_FRICTION`;
- `BREAKS_UNDER_TESTED_FRICTION`;
- `NONPOSITIVE_BASELINE`;
- `INSUFFICIENT`.

Também registra o primeiro nível testado de fricção em que a expectativa fica não positiva.

### UI / stress

A aba Backtest ganhou:

- campo **Slippage adverso por trade (R)**;
- aplicação do slippage em todos os cinco replays, comparador e backtest manual;
- stress adicional configurável de slippage;
- amostra mínima para leitura de sensibilidade;
- resumo e tabela detalhada de custos/slippage;
- exportação `atlasquant_friction_5_*.csv`.

O stress sempre inclui um cenário `ZERO_FRICTION` para referência e depois combina o custo
informado pelo usuário com os níveis de slippage selecionados.

**Regra preservada:** sensibilidade de custos é pesquisa histórica. Não muda parâmetros,
não otimiza setup, não altera Gate, Safety Core, readiness, Runtime ou macro/Fed.

Próximo passo seguro: adicionar análise por sessão/par sob fricção e um teste de robustez de
parâmetros em grade pequena e pré-definida, sem escolher automaticamente "o melhor" conjunto.


## 16/09/2026 UTC — robustez por sessão/par e parâmetros pré-definidos

Estado verificado:

- DEV testada em `65897994707855420ad3d3494a9c9cfe2ad703b1`.
- Quality run `35106389108`: compile gate verde, **615 testes executados, 615 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main permanece em `07b632a28e82a8cdb83f7a5219fc73d6ceb2f42a`; não foi alterada nesta etapa.

### Fricção por sessão e par

`atlasquant_strategy_friction.py` agora também quebra o stress de custos/slippage por:

- sessão;
- par/ativo;
- estratégia;
- cenário de fricção.

Cada segmento mantém sua própria contagem de trades, Gain/Loss/BE, Win Rate observado,
expectativa em R, Net R, Profit Factor, Drawdown e sequência máxima de Loss.

A tela possui o expander **Ver custos/slippage por sessão e par** e exportação CSV específica.

### Robustez de parâmetros pré-definidos

Foi criado `atlasquant_strategy_parameter_robustness.py`.

O objetivo é verificar se o comportamento histórico muda de forma abrupta quando pequenas
variações, definidas previamente no código, são aplicadas. **Não há busca automática do melhor
parâmetro e não existe ranking de variantes.**

Grade fixa atual:

- BOS/CHOCH + OB: alvo 1,5R / 2,0R base / 2,5R;
- FVG: gap mínimo 0 / 0,10 / 0,20 ATR;
- OTE: Sweet 70,5 base / Zone Midpoint / impulso mínimo 0,50 ATR;
- CRT: RR mínimo 0 / 0,50 / 1,00;
- AMD/PO3: acumulação 6 / 8 base / 10 candles.

Cada variante é executada de forma independente com o mesmo histórico e os mesmos parâmetros
gerais de backtest/custos/slippage.

Resumo por operacional:

- `POSITIVE_ALL_PREDEFINED_VARIANTS`;
- `NEGATIVE_ALL_PREDEFINED_VARIANTS`;
- `MIXED_PREDEFINED_VARIANTS`;
- `INSUFFICIENT`.

Também são mostrados:

- número de variantes positivas;
- expectativa da variante BASE;
- pior/melhor expectativa;
- spread de expectativa;
- mínimo/máximo de trades entre variantes.

A amostra mínima por variante é configurável, padrão **20 trades**.

### Proteção de performance e interpretação

A robustez de parâmetros fica **desativada por padrão na UI**, pois roda 15 replays
(3 variantes × 5 operacionais) e pode ser mais pesada em CSVs longos. O usuário ativa
explicitamente quando quiser executar essa auditoria.

**Regra preservada:** nenhuma variante é promovida automaticamente, nenhum "melhor setup" é
selecionado e nenhum resultado altera Gate, Safety Core, readiness, Runtime ou macro/Fed.

Próximo passo seguro: endurecer a robustez com comparação por sessão dentro das variantes e
depois preparar um relatório consolidado de evidências do Backtest, sem transformar métricas
históricas em previsão.


## 16/09/2026 UTC — relatório consolidado de evidências do Backtest

Estado verificado:

- DEV testada em `dca3a278c07068765903731d13b6e1e639569217`.
- Quality run `35107095265`: compile gate verde, **622 testes executados, 622 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main permanece em `07b632a28e82a8cdb83f7a5219fc73d6ceb2f42a`; não foi alterada nesta etapa.

### Relatório consolidado

Foi criado `atlasquant_backtest_evidence.py` para reunir, em uma única visão, as evidências
históricas já calculadas para cada um dos cinco operacionais:

- Backtest geral;
- estabilidade temporal;
- walk-forward OOS;
- sensibilidade a custos/slippage;
- robustez de parâmetros pré-definidos, quando executada.

O relatório **não cria score de qualidade, ranking, recomendação, previsão nem probabilidade de
lucro**. Ele apenas consolida resultados e informa a cobertura dos diagnósticos.

### Cobertura de evidências

Para cada operacional são exibidos:

- trades;
- Win Rate observado;
- expectativa em R;
- Net R;
- Profit Factor;
- Drawdown máximo;
- maior sequência de Loss;
- tamanho da amostra;
- status da estabilidade temporal;
- status walk-forward;
- status de fricção;
- status de robustez de parâmetros;
- quantidade de diagnósticos disponíveis.

A cobertura usa apenas três estados de disponibilidade:

- `COMPLETE` — todos os quatro diagnósticos complementares possuem leitura válida;
- `PARTIAL` — pelo menos um está disponível e algum está ausente/insuficiente;
- `INSUFFICIENT` — nenhum dos diagnósticos complementares possui amostra válida.

**Cobertura não mede qualidade do setup.**

Quando a robustez de parâmetros opcional não é executada, o status fica `NOT_RUN` e a
cobertura permanece parcial, sem inventar conclusão.

### Exportação auditável

A aba Backtest ganhou o bloco **Relatório consolidado de evidências** e duas exportações:

- JSON `ATLASQUANT_BACKTEST_EVIDENCE_V1` com resumo, configurações e tabelas detalhadas;
- Markdown resumido para leitura humana.

O JSON inclui flags explícitas:

- `research_only=true`;
- `no_live_gate_effect=true`;
- `no_profit_probability=true`.

Também preserva as configurações usadas no teste: par, espera/holding, custo, slippage,
estabilidade temporal, walk-forward e parâmetros mínimos de amostra.

**Regra preservada:** o relatório não altera Gate, Safety Core, readiness, Runtime, parâmetros
dos setups ou contexto macro/Fed.

Próximo passo seguro: criar um snapshot reproduzível do conjunto de evidências com fingerprint
do CSV/configuração para permitir comparar duas execuções do Backtest e detectar exatamente
o que mudou, sem promover automaticamente nenhum operacional.


## 16/09/2026 UTC — snapshot reproduzível e comparação de execuções

Estado verificado:

- DEV testada em `624a38f9f7eb3e9c10ab9c14d76a61ee99f92bed`.
- Quality run `35108514542`: compile gate verde, **630 testes executados, 630 OK**.
- Runtime permanece protegida e não foi alterada nesta etapa.
- Main não foi alterada nesta etapa.

### Snapshot reproduzível do Backtest

Foi criado `atlasquant_backtest_snapshot.py`.

Cada execução consolidada pode gerar um snapshot JSON com fingerprints SHA-256 de:

- bytes do CSV original enviado;
- candles OHLC normalizados;
- configurações efetivas do Backtest;
- arquivos centrais do motor/replays/diagnósticos;
- painel de Backtest e Pine Strategies dos cinco operacionais;
- pacote consolidado de evidências.

O `snapshot_id` é derivado do conteúdo desses fingerprints. O horário de criação é apenas
metadado e não altera o identificador, permitindo reproduzir a mesma execução com o mesmo ID.

O snapshot registra separadamente:

- `raw_csv_sha256`;
- `normalized_data_sha256`;
- `settings_sha256`;
- `code_sha256`;
- `evidence_sha256`.

Isso permite diferenciar, por exemplo, um CSV que mudou apenas de formatação de uma alteração
real nos dados normalizados.

### Comparação de snapshots

A aba Backtest ganhou o bloco **Comparar dois snapshots salvos**.

Dois snapshots JSON podem ser enviados para detectar de forma explícita se mudou:

- CSV original;
- dados normalizados;
- configurações;
- código;
- evidências históricas.

Quando as configurações mudam, o diff mostra cada chave com valor anterior e posterior.
Quando as evidências mudam, o diff mostra deltas descritivos de:

- trades;
- expectativa em R;
- Net R;
- Drawdown máximo.

Os deltas não recebem rótulo de melhora/piora e não promovem nenhum operacional.

### Exportações

Após o comparador dos cinco operacionais, a tela agora oferece:

- `atlasquant_snapshot_*.json` com a execução reproduzível;
- `atlasquant_snapshot_diff.json` ao comparar duas execuções salvas.

O schema do snapshot é `ATLASQUANT_BACKTEST_SNAPSHOT_V1`.

**Regra preservada:** fingerprint/diff são ferramentas de auditoria. Não alteram Gate,
Safety Core, readiness, parâmetros, Runtime ou macro/Fed.

Próximo passo seguro: adicionar persistência opcional de histórico de snapshots/execuções e
uma tabela de mudanças entre versões, mantendo a gravação fora de dados operacionais de Runtime.


## 16/09/2026 UTC — histórico local de snapshots e integridade reforçada

Estado verificado:

- DEV testada em `196bb63bf3f834ce0089f9e812ce6516478a0614`.
- Quality run `35110147000`: compile gate verde, **641 testes executados, 641 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`.
- Main permanece em `db17c9f60b3cfbb33597f46e7469ba30c4c1b516`; não foi alterada nesta etapa.

### Integridade fail-closed dos snapshots

Antes desta etapa, o carregamento de snapshots foi endurecido para rejeitar:

- `snapshot_id` adulterado;
- configurações modificadas sem recomputar fingerprints;
- evidências alteradas;
- identity incompleta;
- JSON inválido.

Nesta etapa, a validação também passou a recomputar o hash do manifesto de arquivos de código,
em vez de confiar apenas no `code.sha256` informado no snapshot.

O arquivo `atlasquant_backtest_snapshot_history.py` reutiliza essa validação antes de salvar,
listar, comparar ou exportar snapshots. Arquivos inválidos aparecem como erro de integridade e
não entram na linha do tempo válida.

### Histórico local de pesquisa

Foi criado `atlasquant_backtest_snapshot_history.py`.

O armazenamento padrão é:

`.atlasquant_research/backtest_snapshots`

Esse caminho fica deliberadamente fora de `dados/` e não escreve na branch Runtime.

A gravação é:

- opcional;
- acionada explicitamente pelo usuário;
- atômica via arquivo temporário + rename;
- deduplicada pelo `snapshot_id` derivado do conteúdo.

Também foi criado `.gitignore` para impedir commit acidental de `.atlasquant_research/`.

### Linha do tempo e mudanças consecutivas

A aba Backtest ganhou **Histórico local de snapshots**.

Ela mostra:

- data/hora da execução;
- snapshot id;
- par;
- quantidade de candles;
- início/fim da amostra;
- custo/slippage;
- fingerprints curtos de CSV, dados, configuração, código e evidências.

Também monta uma tabela de mudanças entre snapshots consecutivos, indicando separadamente se
mudaram:

- CSV bruto;
- dados normalizados;
- configurações;
- código;
- evidências.

A tabela ainda mostra quantidade de configurações alteradas e quantos operacionais tiveram
mudanças nas métricas consolidadas.

### Exportação do histórico

O histórico válido pode ser exportado como `atlasquant_snapshot_history.zip`.

O ZIP contém:

- `manifest.json`;
- `timeline.csv`;
- `changes.csv`;
- os snapshots JSON validados.

Em hospedagens com filesystem efêmero, o histórico local pode desaparecer entre deployments.
Por isso o ZIP serve como cópia portátil/auditável.

**Regra preservada:** nenhum snapshot histórico altera Gate, Safety Core, readiness,
parâmetros dos setups, dados operacionais de Runtime ou macro/Fed.

Próximo passo seguro: permitir importar/restaurar um ZIP de histórico validando cada snapshot
antes de incorporá-lo, e depois fechar a camada de auditoria do Backtest para partir para
validação de UI/Runtime final.


## 16/09/2026 UTC — restauração segura do histórico de snapshots

- DEV testada em `77f4ed223676c148c1ac7095bfca0d90f876ecbc`.
- Quality run `35110865542`: compile gate verde, **645 testes executados, 645 OK**.
- Runtime permanece em `7a2ad3e53055fb1ef6091c39442c4c0f5212c3c1`; Main permanece em `db17c9f60b3cfbb33597f46e7469ba30c4c1b516`.

### Importação/restauração fail-closed

`atlasquant_backtest_snapshot_history.py` agora valida e restaura o ZIP exportado pelo histórico. O pacote é lido em memória; nenhum arquivo arbitrário do ZIP é extraído diretamente para o disco. A restauração inteira é validada antes de qualquer gravação.

O pacote é rejeitado se houver ZIP inválido, path traversal, arquivos inesperados, nomes duplicados, criptografia, excesso de tamanho/quantidade, manifesto inválido, contagens/IDs divergentes, snapshot inválido ou corrupção CRC. Limites: 1000 membros, 500 snapshots, 100 MiB descompactados e 10 MiB por snapshot.

Novos arquivos usam o `snapshot_id` completo no nome. Snapshots idênticos já existentes são deduplicados. A UI ganhou **Restaurar histórico exportado (ZIP)** e **Validar e restaurar histórico ZIP**.

**Regra preservada:** a restauração grava somente em `.atlasquant_research/backtest_snapshots`; não altera `dados/`, Runtime, Main, Gate ou Safety Core.

Próximo passo seguro: auditoria final de pré-release da DEV e manifesto de readiness para promoção, sem promover Runtime/Main nesta etapa.
