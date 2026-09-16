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
