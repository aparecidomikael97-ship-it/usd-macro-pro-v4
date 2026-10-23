# A185 — experimento Linux: epoch no VM e escrita WAL, sem homologação

**Data:** 23/10/2026 · **Base:** A185 Native VFS #1479 e ADR #1478, empilhadas sobre A184 #1476. **Código testado:** \`labs/a185/sqlite_vfs_epoch_wal_lab.c\`.

## Resumo

**Resultado experimental:** o hook \`sqlite3_progress_handler(db,1,...)\` pode interromper execução de um statement já preparado, mesmo com leitura cacheada; porém registrar a VFS como padrão **não impede** conexão que seleciona explicitamente a VFS original, e recusar \`xWrite\` apenas do arquivo MAIN_DB **não impede INSERT em WAL**. Cobrir xWrite do arquivo WAL nega essa escrita física específica. Esses resultados **não** demonstram isolamento completo, resistência a host privilegiado ou proteção da implementação Python AION.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.** Nenhum arquivo operacional, \`requirements.txt\`, Worker, deploy, política externa ou serviço real foi alterado.

## Ambiente e reprodutibilidade

- Linux local, GCC14.2.0, SQLite3.46.1 (biblioteca do sistema). **Não executado Windows ou GitHub CI até esta publicação**.
- Código \`sqlite_vfs_epoch_wal_lab.c\` SHA-256 \`097836f7f38fa4d41f690bd7ae8c37afa6b297cd4b104d928f4e234e23750f2d\`.
- 4 runs: 2× \`-O0\`, 1× \`-O2\`, 1× \`-O1 -fsanitize=undefined\`, todos exit 0, sem divergência na saída. Bancos sintéticos gerados em diretórios efêmeros.
- Compilar:

~~~bash
cc -std=c11 -Wall -Wextra -Werror -O0 labs/a185/sqlite_vfs_epoch_wal_lab.c -lsqlite3 -o /tmp/a185_followup
/tmp/a185_followup
cc -std=c11 -Wall -Wextra -Werror -O2 labs/a185/sqlite_vfs_epoch_wal_lab.c -lsqlite3 -o /tmp/a185_followup_O2
/tmp/a185_followup_O2
~~~

### Saída observada (repetida)

~~~text
NATIVE_VFS_ON_DEFAULT=YES PREPARED_WARM_RC=100 REVOKED_CACHED_RC=9 PROGRESS_CALLBACKS=9 RESTORED_RC=100
EXPLICIT_BASE_VFS_BYPASS_RC=0 (SQLITE_OK 0 proves local coverage gap)
WAL_MODE_MAIN_ONLY_DENY_INSERT_RC=0 WAL_XWRITE_DELTA=2 MAIN_XWRITE_DELTA=0 WAL_OPEN=1
WAL_XWRITE_DENY_INSERT_RC=10 DENIED_WAL_WRITES=1
A185_LAB_RESULT=PASS_NEGATIVE_CONTROLS SECURITY_STATUS=INCOMPLETE_STDLIB_BYPASS_AND_EXTERNAL_EPOCH_UNATTESTED
~~~

\`SQLITE_ROW=100\`, \`SQLITE_INTERRUPT=9\`, \`SQLITE_OK=0\`, \`SQLITE_IOERR=10\`. O programa retorna 0 **quando os controles negativos são reproduzidos**, não por considerar a solução segura.

## Matriz técnica

| Cenário | Resultado | Interpretação rigorosa |
|---|---|---|
| Conexão via VFS pública instrumentada, escolhida como padrão do processo | \`NATIVE_VFS_ON_DEFAULT=YES\` | \`SQLITE_FCNTL_FILE_POINTER\` identifica o wrapper do arquivo main. |
| SELECT preparado e em cache, com epoch sintético alterado | \`REVOKED_CACHED_RC=9\`, callback 9 vezes | O hook de **execução** conseguiu interromper esta consulta, não apenas leituras físicas. O epoch é controlado por variável do mesmo processo, não é testemunha independente. |
| Conexão nomeando explicitamente a VFS base | \`EXPLICIT_BASE_VFS_BYPASS_RC=0\` | **RED real:** selecionar base VFS evita o wrapper, mesmo que a personalizada seja a padrão. |
| WAL ativo, \`deny_main_write=1\` | \`INSERT_RC=0\`, \`WAL_XWRITE_DELTA=2\`, \`MAIN_XWRITE_DELTA=0\` | **RED real:** bloquear somente escritas no main DB não bloqueia o WAL. |
| WAL ativo, \`deny_wal_write=1\` | \`INSERT_RC=10\`, 1 escrita WAL negada | A interposição do WAL nega esta operação física; não prova correção de COMMIT incerto, replay ou persistência. |

## Lacunas e riscos de integração

1. \`sqlite3_progress_handler\` com frequência 1 tem overhead; o próprio host com acesso à conexão pode substituí-lo/retirá-lo. Para segurança, precisaríamos verificar permissão em nível de sessão/statement **e** fluxo nativo de storage, com autoridade externa não controlada pelo chamador.
2. Outras VFSs nomeadas explicitamente, ATTACH, conexões de bibliotecas, workers/subprocessos ou outro motor não foram bloqueados. VFS default não é uma sandbox nem torna confiável um processo hostil.
3. Wrapper só aplica bloqueio a \`xWrite\` do MAIN_DB e WAL; não controla todas as chamadas de leitura, \`xSync\`, \`xTruncate\`, SHM/locks, wal_checkpoint, mmap, journal, interrupção de transação, recuperação e janelas TOCTOU. Testes adicionais precisam garantir que o wrapper não introduz corrupção.
4. Este teste foi feito em SQLite C puro, **não** em \`aion_chat/store.py\`, no Outbox/Saga ou em Python sqlite3/Windows. Concluir P0-5/6 seria incorreto.
5. P0-1/2/3/4 continuam dependendo de identidade original, raiz, recibo e custódia monotônica **externa**; o epoch simulado não os resolve.
6. Os cinco casos de \`external-red\` da A184 continuam por resolver; auditoria de dependências A184 continua com 43 achados herdados, corrigidos apenas em propostas Draft paralelas sem merge.

## Próximo passo do Codex — execução, não só documentação

**A)** Decidir como fazer \`sqlite3.connect\` no Python usar sempre a camada nativa, com instruções explícitas de fail-closed se for impossível sem trocar a arquitetura; inventariar todos os caminhos de conexão. **B)** Implementar e reproduzir negação de statement cacheado e de WAL com same-inode/ABA, restart e commit incerto nas plataformas alvo. **C)** Exigir CI Ubuntu/Windows e comparar com os cinco requisitos externos verdadeiramente RED, sem skip, xfail ou renomear testes. **D)** Formular gate de H0/custódia externa para decisão humana, sem contratação.

**É um resultado de engenharia experimental, não aumento de porcentagem de P0 homologados.**


## Adendo — CI real após o código e workflows publicados

**SHA de código e workflows testado:** \`9790c96e2013f888b1fa80ccaff7d601f427850a\`. Os dois arquivos-fonte conferidos em CI usam hash exato esperado; Python normalizou CRLF/LF antes do hash sem alterar a lógica.

| Workflow | Sistema e evidência | Resultado |
|---|---|---|
| [Native VFS Epoch/WAL #39944927477](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39944927477) | Linux, compilações \`-O0\` e \`-O2\`, cenários VM/cache, VFS explícita, escrita MAIN vs WAL | **PASS de contraprovas (1 job)** |
| [Python SQLite Epoch #39944927564](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39944927564) | Ubuntu Python 3.12, SQLite 3.45.1: \`PYTHON_CACHE_REVOKED=DENIED\`; segunda conexão escreve | **PASS** |
| Mesmo run #39944927564 | Windows Python 3.12, SQLite 3.49.1: \`PYTHON_CACHE_REVOKED=DENIED\`; segunda conexão escreve | **PASS** |

**Primeira tentativa Windows preservada:** [#39944702887](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39944702887) falhou na verificação SHA do checkout por conversão CRLF, **antes de executar o Python**. O ajuste em \`9790c96\` passa a verificar bytes normalizados para LF e ambos os SOs passaram. Não interpretar aquele erro como falha SQLite nem apagar a evidência.

**Interpretação:** os resultados verdes provam que os testes reproduziram revogação no VM e bypass de conexão **no escopo e SOs declarados**. No Windows **não foi instrumentado o VFS nativo**, nem foram exercidos ABA/same-inode, xSync/locks/SHM, quedas de energia ou fronteira do Python AION real. Um callback de epoch auto-controlado no processo **não é autoridade independente**, e uma VFS default admite bypass por outra explicitamente nomeada.

**Status:** CI dos experimentos PASS com lacunas de segurança intencionalmente demonstradas. Os cinco requisitos \`external-red\` A184 e os 43 achados do seu stack não foram retestados nesta nova PR, e continuam bloqueios do baseline. **0/6 P0 homologados; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND.** Este adendo é documental, posterior ao SHA testado, sem código operacional alterado.
