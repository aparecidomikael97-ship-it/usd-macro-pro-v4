# A185 — Prova integrada de conexão SQLite real do AION (LAB, cross-OS)

**Data:** 23/10/2026 · **PR:** #1481, empilhada sobre #1480 → #1479 → #1478 → A184 #1476. **Nenhuma mudança operacional:** apenas teste, workflow e este relatório. **0/6 P0 homologados, HARD NO-GO, UNCERTAIN, ZERO_AUTO_RESEND.**

## Prova integrada em Chat, Outbox, Orçamento e Saga

O teste [test_atlasquant_aion_live_connection_boundary_a185_lab.py](../../test_atlasquant_aion_live_connection_boundary_a185_lab.py) importa **módulos reais**, usa banco SQLite **sintético** e confirma os quatro pontos:

| Requisito de prova | Resultado em Ubuntu e Windows | Leitura de segurança |
|---|---|---|
| \`SQLiteChatStore.db\` é o mesmo objeto de \`ExecutionOutbox.db\`, \`CumulativeAuthorityBudget.db\` e \`ExecutionSagaCoordinator.db\` | \`A185_AION_SHARED_DB_HANDLE=CHAT_OUTBOX_BUDGET_SAGA\` | Um hook vinculado à conexão comum alcança essas quatro classes; **não** torna hook obrigatório em todas conexões. |
| \`set_progress_handler(...,1)\` com epoch **sintético** alterado interrompe \`SELECT\` em cache da conexão e \`outbox.list()\` | \`A185_AION_SHARED_HANDLE_CACHE_REVOKED=DENIED...\` | O gancho de execução impede estas consultas específicas mesmo após dados aquecidos; pode ser desativado por quem controla a conexão/processo. |
| Conexão nova \`sqlite3.connect(path)\` não herda o hook e escreve no mesmo banco após revogar epoch da conexão original | \`A185_AION_SEPARATE_SQLITE_CONNECT_BYPASS=WRITES_DURING_REVOKED_EPOCH\` | **Contraexemplo real:** a proteção local não cobre outra conexão. |
| Outra instância \`SQLiteChatStore(path)\` abre novo handle sem herdar hook/epoch do store anterior | \`A185_AION_NEW_STORE_OPEN_BYPASS=UNGUARDED_CONNECTION\` | **Contraexemplo real:** reabrir o store continua fora do guard originalmente aplicado. |

**Os testes são de caracterização: sucesso da suíte quer dizer que os bypasses inseguros estão REPRODUZIDOS, não corrigidos.**

## CI remoto e histórico de correções dos testes

| Execução | Resultado | Causa/evidência |
|---|---|---|
| [#39946845710](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39946845710) | FAIL inicial | O próprio teste importava classe inexistente \`ExecutionSaga\` em vez de \`ExecutionSagaCoordinator\`. Corrigido sem retirar casos. |
| [#39946943782](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39946943782) | Ubuntu PASS; Windows FAIL na limpeza | **Windows executou marcadores de todos os quatro cenários**, mas \`with sqlite3.connect(...) as db:\` não fecha automaticamente a conexão; \`PermissionError [WinError 32]\` na remoção do arquivo. Corrigido com \`parallel.close()\` explícito. |
| [#39947086638](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39947086638) | **4/4 PASS Ubuntu e 4/4 PASS Windows**, jobs SUCCESS | Testes, asserts, logs e exit code conferidos nos dois SOs. SHA exato de código e workflow testado: \`21482f8d28649a836dc071bc40c5abb2c86d10d6\`. |

**Importante:** a falha inicial Windows não deve ser suprimida: prova concretamente que handles SQLite precisam de fechamento explícito antes de remoção/restore naquela plataforma. A correção foi em teste de LAB, **não** em protocolo operacional de restauração.

## Inventário estático limitado e call-sites

- \`aion_chat/store.py\`: \`SQLiteChatStore.__init__\` abre \`sqlite3.connect\` nativo; \`backup_to\` cria **outra** conexão para destino; \`_validate_database_bytes\` abre \`:memory:\` offline e valida conteúdo retido. São escopos distintos.
- \`aion_chat/staged_store.py\`: a cada operação \`OperationScopedSQLiteChatStore\` abre uma nova instância \`SQLiteChatStore\` dentro da thread e fecha em \`finally\`; o hook colocado em outra instância **não migra automaticamente** para essa abertura.
- \`atlasquant_aion_execution_outbox.py\`, \`atlasquant_aion_cumulative_authority_budget.py\` e \`atlasquant_aion_execution_saga.py\`: compartilham \`store.db\` no caso inspecionado. Isso é um fato de objeto no teste, **não** garantia de que todo caminho do produto passe por esse mesmo store.
- Conexões de processos externos, código privilegiado, bibliotecas com VFS explícita e restore após crash continuam fora da prova. Inventário não exaustivo dos ~1.163 arquivos Python do ramo.

## Próxima tarefa técnica — sem aceitar solução incompleta

1. **Gate obrigatório em TODA abertura e uso de conexão**, incluindo \`SQLiteChatStore\`, \`OperationScopedSQLiteChatStore\`, Outbox/Saga, backup e restore, com recusa em falta/ambiguidade de epoch. Não é suficiente monkey-patch de \`sqlite3.connect\` ou uma VFS marcada padrão — atacante pode nomear VFS base, abrir processo alternativo e reapresentar arquivos.
2. **Autoridade do epoch fora do mesmo host**, atestada e com monotonicidade H0. \`epoch={"authority":2}\` dentro do teste é uma fixture sintética, manipulável. P0-1/2/3/4 permanecem abertos.
3. **Unir operação e commit ao gate nativo**: VFS real, WAL, SHM, locks, page cache, backup/restore, ABA, same inode, crash após COMMIT sem ACK e Windows adversarial exercido, não só \`OS_DENIED\`.
4. **Auditar de verdade todos os call-sites** e provar que uma nova conexão não consegue efetuar I/O crítico sem ser rejeitada; se Python stdlib/arquitetura atual não oferecer essa propriedade, escolher alteração de arquitetura aprovada, sem declarar homologação a partir de um hook sintético.
5. Preservar CI RED de cinco requisitos externos e auditoria das 43 vulnerabilidades do stack A184, que **não foram reexecutados nesta PR**. Sem skip/xfail/continue-on-error nos requisitos.

## Guardrails

PR #1481 permanece Draft, baseada em #1480; nenhum merge, deploy, Worker, broker, serviço de terceiros, contratação, chave ou operação real. Quatro testes por SO fazem caracterização com SQLite real, mas não atestam raiz de confiança nem resultado de commit. **P0 = 0/6; HARD NO-GO; ZERO_AUTO_RESEND; UNCERTAIN permanece obrigatório.**
