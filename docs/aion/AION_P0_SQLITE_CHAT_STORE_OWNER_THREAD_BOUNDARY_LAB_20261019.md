# P0 SQLiteChatStore — guarda de ownership por thread, somente LAB

19/10/2026. **Não é homologação de P0 ou autorização de produção.** O AION mantém `HARD NO-GO`, `0/6 P0 homologados`, Worker OFF, ZERO_AUTO_RESEND e módulos externos não inscritos.

## Problema auditado no original

`aion_chat/store.py` A118 original, Git blob `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`, usa `sqlite3.connect` com `check_same_thread=True` padrão, corretamente. Porém `storage_health(deep=True)` em outra thread capturava `sqlite3.ProgrammingError` como `sqlite3.DatabaseError`, registrando `_health_state=FAILED`, apesar de a thread errada, não corrupção física, causar o erro. `require_healthy()`, `backup_to()`, `wal_checkpoint()` e operações de leitura/escrita também retornavam falhas genéricas ou mudavam o estado de saúde. Uma tentativa na thread errada poderia comprometer o diagnóstico do store local, sem ação externa.

## TDD: matriz congelada ANTES do patch

- Branch `lab/aion-p0-sqlite-store-owner-thread-20261019` derivada de `015b4cf34b8be0251ba3bef5bb89ac69c08d8ebb` (Outbox com guarda por objeto Thread).
- 15 contratos `test_aion_p0_sqlite_chat_store_owner_thread_lab.py`, commit `20ec5fc8547d90c722113752d3c4226aca9fa96e`.
- 1 a 12: health, require_healthy, close, WAL checkpoint, backup, get/create/list conversation, append message, archive, list messages, transação externa pendente (sem rollback). Todos requerem `StorageUnavailableError(SQLITE_STORE_CONNECTION_THREAD_MISMATCH)`, **sem I/O de SQLite**, sem alteração de estado de saúde e sem efeitos.
- 13 a 15: nova conexão própria de outra thread segue permitida, backup/health no dono permanecem saudáveis, escrita no dono depois de chamada negada continua.
- `aion_chat/store.py` original NÃO possuía essas proteções. [RED #39316307777](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39316307777): Ubuntu job `118278592328` registrou 9 ERROR + 4 FAIL = **13/15 cenários não atendidos**, apenas 2 PASS. Evidências incluem `sqlite3.ProgrammingError`, `StorageUnavailableError(staging store is not healthy: DATABASE_ERROR:ProgrammingError)` e ausência de negação na consulta de saúde. O RED comprova lacuna de contrato; **não comprova perda de dados ou bypass externo**.

## Patch mínimo na branch isolada

Commit `2eed980be36143535ef94e3f52f53852030708b1`, altera SOMENTE `aion_chat/store.py`:
- Na criação do SQLiteChatStore, registrar o **objeto** `threading.current_thread()` como dono da conexão (não ID numérico reutilizável).
- `_require_connection_thread()` em caso de outra thread levanta `StorageUnavailableError("SQLITE_STORE_CONNECTION_THREAD_MISMATCH")` ANTES de consultar SQLite, fechar conexão, alterar health, começar/reverter transação, checkpoint ou backup.
- Guard central em `_require_open`, `storage_health` e `close`; guard explícito antes de context managers de `archive_conversation`, `add_attachment_metadata`, `save_checkpoint` e `save_context_summary`.
- Preserva `check_same_thread=True`, WAL, busy timeout, commits, locks, filas, credenciais, mecanismos de producer hard-stop, o Outbox e chamadas externas. Não adiciona threads/IO/executor.

## Validação verde (não equivale à Quality canônica completa)

[GREEN #39316487626](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39316487626), commit/head `2eed980be36143535ef94e3f52f53852030708b1`, ambos jobs `success`:
- **Ubuntu** job `118279191701`: 15 novos + 12 Outbox thread + 7 nested + 8 concorrência/restauração + 22 A110/A63/A64/A65 + 2 de health WAL/concurrent separate handles = **66/66 PASS**.
- **Windows** job `118279192191`: mesmos 66/66 PASS.
- **132 execuções de casos / 66 distintos**, todos os controles antigos do workflow passaram; SHA do Outbox `cd78ed43ad63888408eb599e28379c193c541de2` não foi modificado, baseline do store A118 fixado na CI.

## Limites reais e pendências sem disfarce

1. `SQLiteChatStore.db` ainda expõe a conexão subjacente; classes/callers que usam `store.db` diretamente **não passam necessariamente por este guard** e ainda podem gerar `ProgrammingError`. Auditoria dos chamadores e controle de interface necessários.
2. Sem isolamento operacional real entre processos/hosts, teste físico de queda de energia/reboot ou prova de durabilidade de high-water; a restauração de backup SQLite antigo ainda apaga `UNCERTAIN` e permite re-claim local após restore. Esse resultado permanece deliberadamente coberto pelo teste.
3. Guards na mesma thread não resolvem interleaving de execuções lógicas que compartilham conexão, nem transações aninhadas (o Outbox ainda bloqueia composição com `OUTBOX_NESTED_TRANSACTION_UNSUPPORTED`), nem fonte independente de efeitos.
4. `restore_from_backup()` é uma função de classe sem conexão previamente vinculada; verificar seu trust anchor é questão separada do ownership de thread.
5. A matriz cobre alguns endpoints representativos e regressões antigas. **Não foi executada a suite Quality/Security integral**, nem homologação dos dois P0 canônicos históricos. Passar nos testes não significa que todos os call sites ou threads de shutdown tenham sido ajustados.
6. A negação explícita de `close()` em thread errada protege contra manipulação do handle, mas exige que hosts/serviços agendem cleanup na thread dona. Revisar integração antes de merge futuro.

**Próximo trabalho prioritário:** mapear call sites de `store.db` e encerramento de conexões vindos de outros threads; depois corrigir com design seguro e testes de compatibilidade, sem habilitar `check_same_thread=False`. A necessidade de witness externo para rollback continua independente.

Nenhum merge, deploy, reenvio, Worker, provedor externo, custo novo ou operação de usuário foi realizado.
