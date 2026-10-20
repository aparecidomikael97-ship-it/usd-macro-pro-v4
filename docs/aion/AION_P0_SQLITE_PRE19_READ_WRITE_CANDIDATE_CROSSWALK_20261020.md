# AION P0 SQLite — dois candidatos antigos, dois contratos diferentes

**Data: 20/10/2026** · **HARD NO-GO** · **0/6 P0 homologados** · **nenhum efeito externo autorizado**.

## Novidade: encontrei os primeiros candidatos anteriores às suítes de 19 de outubro

A auditoria [PR #1345](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1345) comprovou o RED/GREEN do `SQLiteChatStore` em 19/10, mas corretamente deixou **os dois P0 originais sem IDs**. Agora identifiquei duas trilhas verificáveis de **10 e 14 de outubro**, anteriores àqueles testes. Elas não devem ser confundidas nem declaradas automaticamente equivalentes aos P0 originais.

### Candidato A — leitura/uso do SQLite após rerun Streamlit

[PR Draft #1195](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1195), criado em **10/10/2026**, identifica que `atlasquant_aion_chat_host_staging.get_or_create_staged_store` guarda uma instância de `SQLiteChatStore` nativo no `session_state`. Após rerun em outra thread, `storage_health` tenta ler pela thread incorreta, reportando `StorageUnavailableError: DATABASE_ERROR:ProgrammingError`. O PR introduziu a alternativa `OperationScopedSQLiteChatStore`, que abre e fecha a conexão na thread de cada chamada e não abandona a referência em caso de falha de fechamento. [CI #38089857958](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38089857958) **SUCCESS**, [Quality #38089858004](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38089858004) **SUCCESS**, ambos no HEAD `e0e249db64c1bef32ff47f0048a9900542dd144a` e seleção histórica então aplicada.

**Limite/risco atual:** na branch base desta rodada, `atlasquant_aion_chat_host_staging.py` **ainda usa `SQLiteChatStore` diretamente** e `aion_chat/staged_store.py` **não existe**. Já `SQLiteChatStore` contém a proteção owner-thread adicionada em 19/10: o cross-thread **falha fechado**, sem efetuar read/write. Isto evita uso inseguro da conexão, mas **não recupera a disponibilidade** da interface STAGING em rerun noutra thread. A correção candidata de 10/10 não deve ser presumida integrada apenas porque sua própria CI foi verde.

### Candidato B — escrita local parcialmente confirmada entre Saga e Outbox

[PR Draft #1281](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1281), de **14/10/2026**, possui RED de verdade [CI #38583150088](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38583150088): **8 testes, 2 FAIL**. Uma exceção durante a gravação de evento Saga ou `UPDATE` de step deixava registros `action_outbox`/`action_decisions` duráveis enquanto Saga permanecia `PLANNED`. [CI GREEN #38584114098](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38584114098): **10/10 PASS**, combinando `BEGIN IMMEDIATE` externo e `SAVEPOINT` para Outbox dentro da transação Saga. Quality e Security selecionadas ainda estavam RED em [#38584114177](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38584114177).

**Estado na branch LAB atual:** `atlasquant_aion_execution_outbox.py` contém `SAVEPOINT aion_outbox_enqueue` e `test_atlasquant_aion_saga_outbox_atomic_a61.py` existe; a contenção local está presente e será reexecutada. Isso **não** prova `COMMITTED_EFFECT` externo nem demonstra que o P0 de escrita originalmente reportado tinha exatamente esse ID.

## Classificação e próximos gates

| Família | Evidência obtida | Exige ainda |
| --- | --- | --- |
| Host SQLite STAGING entre reruns (READ candidate) | Repro 10/10 e correção candidata aprovada em sua própria branch; host atual ainda armazena conexão nativa | Teste diagnóstico atual Ubuntu/Windows e revisão para eventual integração isolada sem merge direto |
| Atomicidade Saga/Outbox (WRITE candidate) | RED 2 FAIL e GREEN 10 PASS em 14/10; SAVEPOINT existe atualmente | Regressão real no HEAD atual, no mesmo contrato, e Quality/Security completas |
| Os **dois P0 originais** do registro dos seis | **Não foi encontrado o mapeamento original inequívoco** | Documento/issue anterior identificando run/job/stack e correspondência explícita a READ e WRITE |

**Prioridade de engenharia:** corrigir/avaliar concretamente a disponibilidade do host STAGING sob múltiplas threads sem desativar `check_same_thread`, **mas somente por PR candidato independente sujeito a revisão**, sem tocar o Worker ou homologar o P0. Paralelamente, preservar o controle atômico `BEGIN IMMEDIATE` / `SAVEPOINT` que já impede parte dos registros locais órfãos. O [novo issue #1346](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1346) separa formalmente esses dois riscos dos 32 casos Outbox/Saga da issue #1329.

## Verificação

`tests/test_aion_p0_sqlite_pre19_read_write_candidates_lab.py` contém **9 testes** que usam o `atlasquant_aion_chat_host_staging` REAL, `SQLiteChatStore` REAL com arquivos temporários, `ThreadPoolExecutor` e testes A61 reais. **O PASS dos cinco testes de negação de rerun é evidência de uma indisponibilidade atual, não de correção implementada.** Nenhum teste cria tráfego, usa provider, credenciais reais ou envia ações. Os 32 ERROR canônicos continuam `OPEN_NOT_WAIVED`.

**Status:** HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, nenhuma PR aprovada para merge/deploy, 0/6 P0 homologados.