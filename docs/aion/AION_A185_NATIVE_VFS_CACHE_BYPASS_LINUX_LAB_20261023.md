# A185 — SQLite VFS nativa: prova de execução e dois contraexemplos

**Data:** 23/10/2026 · **Base:** PR Draft #1478, empilhada na A184 #1476. **Fonte testado:** labs/a185/sqlite_vfs_spike.c.

**LAB APENAS — 0/6 P0 homologados, HARD NO-GO, UNCERTAIN, ZERO_AUTO_RESEND.** Esta prova não altera AION em execução; não autoriza merge ou deploy.

## Execução local verificável

Sistema Linux; compilador GCC 14.2.0; biblioteca SQLite 3.46.1. SHA-256 do fonte testado: 41fcd9c35e87a0b531f511030483ae79475c495bcbac0176e03044335826d5e8. Três execuções com -O0 e uma com -O2; todas terminaram com exit=0 e saídas idênticas. **Ainda não houve CI GitHub nem Windows.** Sem novas dependências, redes, contas, credenciais ou dados de produção. Cada teste cria base sintética de 10.000 linhas em diretório temporário.

Comandos:

~~~bash
cc -std=c11 -Wall -Wextra -Werror -O0 labs/a185/sqlite_vfs_spike.c -lsqlite3 -o /tmp/a185_vfs_spike
/tmp/a185_vfs_spike
cc -std=c11 -Wall -Wextra -Werror -O2 labs/a185/sqlite_vfs_spike.c -lsqlite3 -o /tmp/a185_vfs_spike_O2
/tmp/a185_vfs_spike_O2
~~~

Saída literal reproduzida:

~~~text
NATIVE_HANDLE_SAME_VFS=YES MAIN_OPENS=1
WARM_RC=100 CACHE_AFTER_DENY_RC=100 CACHE_EXTRA_XREAD=0 COLD_AFTER_DENY_RC=10 DENIED_READS=1
WRITE_AFTER_DENY_RC=10 DENIED_WRITES=2 MAIN_WRITES=2 JOURNAL_OPENS=1 WAL_OPENS=0
DEFAULT_VFS_WHILE_GUARD_DENIES_WRITE_RC=0 (SQLITE_OK=0 is bypass)
RESULT=PASS_NATIVE_IO_INTERCEPTION; SECURITY_RESULT=INCOMPLETE_CACHE_AND_DEFAULT_VFS_BYPASSES
~~~

Constantes SQLite: SQLITE_ROW=100; SQLITE_IOERR=10; SQLITE_OK=0. O processo retorna zero se **os comportamentos inseguros esperados foram REPRODUZIDOS**, não se o aplicativo está seguro.

## Resultados: o que passou e o que continua vulnerável

| Experimento | Evidência real | Conclusão |
|---|---|---|
| File pointer da conexão nativa (SQLITE_FCNTL_FILE_POINTER) | NATIVE_HANDLE_SAME_VFS=YES | O wrapper está ligado à conexão nativa SQLite deste teste, não a um descritor paralelo. |
| SELECT em página não cacheada depois de negar leitura | COLD_AFTER_DENY_RC=10, DENIED_READS=1 | O gate de xRead consegue negar esta leitura física. |
| SELECT repetido na mesma transação após revogar acesso | CACHE_AFTER_DENY_RC=100 e CACHE_EXTRA_XREAD=0 | **Contraexemplo:** a leitura cacheada continuou sem passar pelo VFS. |
| UPDATE/COMMIT depois de negar escrita | WRITE_AFTER_DENY_RC=10 e DENIED_WRITES=2 | A VFS interceptou a escrita física deste fluxo. Não atesta commit/recovery. |
| Nova conexão pela VFS padrão enquanto política instrumentada está negada | DEFAULT_VFS_WHILE_GUARD_DENIES_WRITE_RC=0 | **Contraexemplo:** a conexão não instrumentada escreveu sem consultar o guard. |

Esses dois bypasses demonstram a insuficiência do **candidato** de segurança, não um defeito do próprio SQLite.

## Limites essenciais

- O wrapper experimental só decide xRead/xWrite do MAIN_DB e parte de xFetch. Delega locks, journal/WAL/SHM, xSync, xTruncate, xFileControl e outras operações. Não protege cache, reabertura não instrumentada, transação completa ou host privilegiado.
- A prova é somente em journal DELETE; WAL_OPENS=0. Não testa WAL, sidecars, multi-processo, ABA, same-inode overwrite, perda de resposta após COMMIT, power loss ou restauração física.
- Não usa APSW, APIs privadas CPython nem altera os 76 específicos A184, 132 regressões por SO, 93 SQLite por SO ou cinco requisitos externos FAIL.
- Nenhuma ligação operacional com os caminhos Python AION (aion_chat/store.py, Outbox, Saga, Worker). Não autoriza assumir que os bypasses estão resolvidos no núcleo.
- Os 43 achados da auditoria de dependências A184 continuam como limitação do stack; a remediação é trabalho separado.

## Próxima correção que o Codex precisa DEMONSTRAR

1. **Autorização antes de cada statement/transação:** negar leitura cacheada após revogação/epoch, não apenas I/O VFS.
2. **Cobertura completa de conexões:** detectar/bloquear conexões por VFS padrão e outros caminhos, com testes de bypass no próprio programa.
3. **Proteção nativa efetiva:** testar VFS real com WAL/SHM, Windows/Linux, concorrência, renomeação ABA, overwrite same inode, commit incerto e recuperação.
4. **Sem confundir guarda local com autoridade externa:** P0-1/2/3/4 seguem exigindo identidade, proveniência/recibo, reserva original e custódia monotônica independente.
5. **Evidência e gates:** CI completo sobre SHA testado, falhas externas explícitas, Quality/Security sem relaxamento. Resultado NOT_EXERCISED do Windows não equivale a PASS.

**Veredito LAB:** avançamos da análise documental para o teste do arquivo REAL do motor e descobrimos dois caminhos em que um guard incompleto seria contornado. **Nenhum P0 fechado, nenhuma alteração de produção.**
