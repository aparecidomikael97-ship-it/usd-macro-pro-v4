# AION P0 — perícia de causalidade SQLite: incidente anterior versus suíte LAB de 19/10

**20/10/2026 | HARD NO-GO | 0/6 P0 homologados.** Este registro preserva a diferença entre a **causa verificável de uma falha posterior de testes LAB** e a identificação dos **dois P0 originalmente relatados** (leitura e escrita), que continuam sem run/método/stack exato mapeado.

## Evidência nova obtida do histórico Git

O GitHub conserva os commits de correção e suas relações pai/filho. O run [#39316307777](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39316307777) executou uma suíte de 15 testes `test_aion_p0_sqlite_chat_store_owner_thread_lab.py`, em **Ubuntu e Windows**. Foram **4 FAIL, 9 ERROR e 2 PASS** em cada SO. Os logs revelam `sqlite3.ProgrammingError` ao acessar conexões por outra thread e respostas de erro que não continham `SQLITE_STORE_CONNECTION_THREAD_MISMATCH`.

O commit seguinte [`2eed980`](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/commit/2eed980be36143535ef94e3f52f53852030708b1) tem como **pai exato o HEAD do run RED** (`4f9c6acb4d3d1c081ad13c98434c52bdd78b861e`) e muda **somente** `aion_chat/store.py` (+17/-0). O código adiciona `_connection_owner_thread`, `_require_connection_thread()` e checagens antes de leitura, escrita, close e saúde. **Não desativa `sqlite3` check_same_thread**. O arquivo de testes manteve o SHA Git `878efd12a4348cbc8beef3093b9685116ce1a8cd` e passou depois no [run LAB #39416850779](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39416850779), Ubuntu e Windows. Esse é um RED/GREEN **de apoio** bastante específico.

Há outros dois commits produtivos na sequência LAB, ambos exclusivamente em `aion_chat/store.py`:
- [`0f0ba9f`](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/commit/0f0ba9f033c2d1e257e542b4bc695a595c680eac), **+50/-0**, bloqueia `restore_from_backup` de **origem ou destino** que contém tabelas do ledger de execução sem testemunha independente. Nenhum hash local ou `PRAGMA quick_check` prova o high-water externo.
- [`543a47e`](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/commit/543a47e0d3a897a6a5a6903826d6255307d18d37), **+10/-7**, inspeciona o conteúdo efetivamente visível do SQLite/WAL quando o destino existe e mantém bloqueio sobre WAL/SHM órfãos. Continua sem comprovar que não houve rollback manual.

## Por que “original” no nome do teste não encerra o P0

O histórico de criação dos testes demonstra a diferença:
- `test_aion_p0_original_sqlite_compat_concurrency_restore_lab.py` surgiu somente em **19/10 às 19:41 UTC**, no commit `6df1cc7e...`, para observar concorrência, transação e restauração.
- `test_aion_p0_sqlite_chat_store_owner_thread_lab.py` surgiu às **20:04 UTC**, `20ec5fc...`.
- `test_aion_p0_sqlite_execution_restore_hardstop_lab.py` surgiu às **20:42 UTC**, `042d83d...`.

Os dois P0 de leitura/escrita foram listados no registro canônico do projeto com `canonical_tracker_id=null`. **Ter nome “original” em um ensaio criado posteriormente não fornece ID do incidente original**. Uma suíte posterior verde, sozinha, não resolve a falta desse nexo.

O pacote traz [matriz JSON versionada](AION_P0_SQLITE_ORIGINAL_LAB_LINEAGE_20261020.json) e `tests/test_aion_p0_sqlite_original_vs_lab_commit_lineage.py`, com **12 verificações de commits, pais, patches, hashes, contagens e preservação do NO-GO**. Todos operam exclusivamente sobre objetos Git do checkout: nenhuma ação externa.

## Próxima prova que realmente reduz a lacuna

Localizar **uma fonte anterior à criação das suítes de 19/10** com definição exata do erro SQLite-read e SQLite-write (teste, método, stack, SHA, job), identificar as mudanças que o resolveram, e reexecutar o *mesmo contrato* RED antes/GREEN depois. Não promover o pareamento 15-case como substituto. Se os registros nunca documentaram esses IDs, marcar **INDETERMINADO** e solicitar revisão independente sem afirmar homologação.

A validação futura deve incluir Quality e Security canônicas sem exclusões/waivers, Windows físico, power-loss/WAL e prova externa de produtor/H0 antes de execução protegida. **A demonstração de negação pré-adaptador não é um recibo externo autenticado**.

**32 ERROR Outbox/Saga `OPEN_NOT_WAIVED` | Quality histórica 51 FAIL + 34 ERROR | Worker OFF | ZERO_AUTO_RESEND | sem merge, deploy, fornecedor, IAM, SMS ou gasto.**
