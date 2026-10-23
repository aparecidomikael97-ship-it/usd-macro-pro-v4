# A185 / P0-5 e P0-6 — decisão preliminar SQLite LIVE (somente LAB)
**Data:** 23/10/2026. **Base:** A184 #1476, commit `1f024c0d4e9e65a3fd3c6c4d2d83c5221b77ba11`, código testado `af5739c010ddf5cb28a64fad5b5c386b96ed2b3c`. **Vinculado à missão** [#1477](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1477). **Status: pré-flight estático + documentação oficial, SEM prova executada de VFS.** 0/6 P0 homologados; HARD NO-GO; UNCERTAIN e ZERO_AUTO_RESEND.

## 1. Causa comprovada e o que A184 não provou
A184 trouxe proteção de recuperação **offline**: bytes capturados de `os.open`, schema validado no SQLite `:memory:`, somente esses bytes publicados, falha posterior ao replace -> UNCERTAIN. Isto **não liga atomicamente** o arquivo de `os.open` à conexão `sqlite3.Connection` **LIVE** que realmente faz SELECT/INSERT/COMMIT.

No Ubuntu, em [CI A184 #39902967998](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39902967998) aparece `A183_NATIVE_SAME_NAME_ABA=WRONG_FILE_READ_PATH_CHECK_PASSED`. Windows retornou `OS_OR_FACADE_DENIED`/`OS_DENIED`; isso só mostra bloqueio no SO naquele cenário, não prova a fronteira da aplicação. A suíte `external-red` ficou com **cinco FAIL por SO**, incluindo read e write de restore same inode. Citar stdout isolado jamais substitui assertions, exit code e teste adversarial real.

### Modelo de ameaça irredutível
- Atacante/controlador do host modifica, troca, renomeia, restaura ou retrocede conteúdo de SQLite e `-wal/-shm/-journal` entre abertura, validação, leitura e escrita; pode repetir caminho/nome/inode e restaurar um estado estruturalmente válido.
- Aplicação deve **negar mudança sem prova de identidade/conteúdo/epoch e não reautorizar nem reexecutar uma intenção incerta**. Observar `stat`/hash/path em outro descritor não oferece prova de que SQLite usou os mesmos bytes.
- Autoridade que controla o próprio host, banco e raízes pode retroceder todas as provas locais. **P0-1/2/3/4 exigem componente independente**, mesmo que um VFS local melhore P0-5/6. SQLite VFS não é antirollback externo.

## 2. Evidência de interface pública — fontes primárias
1. SQLite [VFS OS Interface](https://www.sqlite.org/vfs.html): `sqlite3_vfs.xOpen` devolve o `sqlite3_file` efetivamente usado; `sqlite3_io_methods` executa `xRead`, `xWrite`, `xSync`, `xLock`, `xClose`. **Esta é a fronteira tecnicamente correta para observar EFEITOS DO MOTOR**, se houver acesso seguro e interposição completa.
2. SQLite [sqlite3_file_control](https://www.sqlite.org/c3ref/file_control.html): operação `SQLITE_FCNTL_FILE_POINTER` expõe `sqlite3_file*` **na C API**, não diretamente no `sqlite3.Connection` Python padrão. Pegar ponteiro privado da estrutura CPython via `ctypes` não é opção aprovada.
3. [APSW VFS](https://rogerbinns.github.io/apsw/vfs.html): wrapper Python expõe `VFS` e `VFSFile`, inclusive herança e `xOpen`, conexões abertas com `apsw.Connection(..., vfs=...)`. **Candidato de LAB**, não API existente na implementação A184 nem garantia de equivalência/performance/risco com stdlib.
4. SQLite [Backup API](https://www.sqlite.org/backup.html): backup online consistente via conexão SQLite; não é a mesma coisa que backup/restore de bytes offline de 16 MiB. [WAL](https://www.sqlite.org/wal.html): WAL é estado persistente do banco, não pode ser descartado/copiado separadamente sem protocolo. [How To Corrupt](https://www.sqlite.org/howtocorrupt.html): locks e arquivos auxiliares são essenciais; renomear o arquivo vivo pode comprometer consistência.
5. [Python stdlib sqlite3](https://docs.python.org/3/library/sqlite3.html): fornece `connect`, transações, `backup` e `deserialize`; **não** fornece diretamente método público Python para inspeção/interposição do `sqlite3_file` da conexão viva.

## 3. Inventário de fronteiras do repositório, inspecionado no HEAD A184
| Local/call-site | Efeito atual | Prova que falta |
|---|---|---|
| `aion_chat/store.py:341–384` / `:348` | `SQLiteChatStore.__init__` abre `sqlite3.connect(str(self.path))`, configura WAL e schema; conexão é separada da captura offline. | Abrir o mesmo handle efetivo aceito pelo guard; barrar read/write com ligação à autoridade retida. |
| `aion_chat/store.py:395–483` | `storage_health` e `wal_checkpoint`, PRAGMA quick_check/WAL. | Atestar que checks observam **o mesmo banco vivo** da operação, inclusive ABA/restauração simultânea. |
| `aion_chat/store.py:485–534` | `backup_to` usa checkpoint + backup SQLite para temporário e normaliza artefato offline DELETE. | Concorrência real, destino, locks, WAL, falhas de energia, limites de tamanho e schema de Outbox/Saga. |
| `aion_chat/store.py:535–559` | `restore_from_backup` valida/captura origem, publica bytes; exige offline/quiescente, que **não equivale a provar** ausência de outros processos. | Gate de exclusão real e atestação do destino/epoch; ACK incerto sem reexecução. |
| `aion_chat/store.py:222–339` | `_validate_database_file` usa `os.open`; `_publish_database_report` faz fsync/replace. | Essa fronteira **não é** VFS do SQLite live; não elevar êxito de backup/restore offline à autorização do banco ativo. |
| `aion_chat/store.py:662–689` | `append_message` inicia `BEGIN IMMEDIATE`. | Abrangência dos efeitos de commit, sidecars e crash após resultado incerto. |
| `atlasquant_aion_execution_outbox.py:290–~528` | `enqueue`, claims e lease em `self.db`, transações `BEGIN IMMEDIATE`. | Vínculo do banco usado no fluxo que autoriza/retém decisão. |
| `atlasquant_aion_execution_outbox.py:621–828` | `dispatch_claimed` reserva e persiste UNCERTAIN **antes** de efeito; reconciliação nega reenvio cego. | Recuperação mantém esse mesmo estado durável após trocar banco/host/epoch; observar o resultado pós-commit. |
| `aion_chat/pinned_snapshot_a183_lab.py` | `os.open`→captura→SQLite `:memory:` somente leitura. | Artefato útil para comparação offline, mas **não é substituto do SQLite operacional**. |

**Escopo deste inventário:** os arquivos acima foram lidos de forma estática; **não** foi feita análise de todos os call-sites do repositório. Codex deve varrer explicitamente módulos Saga, adapters, Worker desativado, threads, startup/restart e outros `sqlite3.connect` antes de declarar cobertura completa. Referências de linhas são do head A184 documentado, podem deslocar após mudanças.

## 4. Alternativas e decisão preliminar (não autorização de migração)
| Caminho | Prova que pode oferecer | Custos/limitações não resolvidos | Parecer LAB |
|---|---|---|---|
| **A — VFS instrumentado, usando API pública suportada (ex.: APSW em sandbox)** | Hook no `xOpen/xRead/xWrite/xSync` efetivo, evidência do fluxo REAL lido/gravadado, observação de journals e WAL; retorno de falha dentro do motor. | Migração `sqlite3`↔APSW não trivial (transações, rows, cursor, parametrização, threads, backup, callbacks, integração CI, ABI/versão SQLite, Windows). Sob controle hostil do kernel/host não comprova monotonicidade externa. VFS que herda base requer cobrir locks/WAL sem contorná-los. Dependência nova somente em ambiente efêmero **se autorizada**; sem tocar requirements. | **Preferir para experimento A185 isolado**, porque testa a fronteira nativa que hoje falta; **não** migrar produção na PR. |
| **B — arquitetura sem SQLite live na fronteira crítica: snapshot imutável + ledger append-only + publicação controlada** | Reduz janela de arquivo mutável e diferencia estado observado do objeto publicado; pode separar leitura de publicação. | Ledger é local/restaurável; precisa consenso/autoridade externa e controle transacional sobre todos os efeitos; power loss/conexões concorrentes, atomicidade e replay continuam. Reescrita mais ampla; não presume ganho de confiabilidade sem testes. | Plano de contingência/ADR se A for inseguro ou incompatível; não presumir que cópia de bytes resolve commit. |
| **C — módulo nativo C/C++ com SQLite C API** | `sqlite3_file_control` e VFS nativos são APIs públicas de SQLite, acessíveis com extensão adequada/ligação própria à conexão. | Distribuição/compilação/ABI e manutenção em Windows/Linux; acesso arbitrário via ponteiros CPython **proibido**. | Considerar somente se APSW LAB não permitir atestar a propriedade necessária. |

**Decisão proposta:** executar primeiro um *spike* VFS (A) com casos negativos e cobertura de file kinds, em LAB isolado e dependências de teste não integradas ao runtime. Resultado negativo é um resultado válido. Depois submeter escolha definitiva ao responsável humano, comparando custo/portabilidade e P0-5/6.

## 5. Critérios falsificáveis para o spike A185
**Pré-condição:** teste deve instalar VFS com nome explícito, criar conexão *por essa VFS* e provar que a consulta/commit atravessa o wrapper; logar classe do arquivo (main, WAL, journal, SHM quando aplicável), identificador do OPEN e operação R/W/SYNC, sempre sem segredos. Não aceitar como prova um `os.open` paralelo nem um `PRAGMA database_list` isolado.

- **G1 / identidade de leitura:** injetar diferença A↔B após guard/pathname e antes da operação `SELECT` do **mesmo banco vivo**; confirmar recusa do gate ou leitura retida de A com protocolo autorizado. Se SELECT ler B após validação de A e disser OK, **FAIL**.
- **G2 / identidade de escrita:** injetar ABA com mesmo nome, restore de conteúdo com mesmo inode e WAL conectado antes/durante `BEGIN IMMEDIATE`/`COMMIT`; nenhuma gravação em destino/epoch não autorizado. Se ACK de COMMIT/REPLACE for perdido, resultado **UNCERTAIN**, sem novo send.
- **G3 / concorrência:** dois processos com leitores/escritores, checkpoint, backup, restauração e sidecars presentes; se interposição quebrar isolamento SQLite/locking, **FAIL**. Windows `OS_DENIED` fica **NOT EXERCISED**, requer outro ensaio que alcance o caminho crítico.
- **G4 / recuperação:** crash simulado entre journal/WAL sync, commit, publicação e ACK, reinício; estado pode ser CONFIRMADO apenas com prova de commit e vínculo à custódia monotônica; se desconhecido, negar efeito/reenvio.
- **G5 / prova de escopo:** lista de calls que passam pelo VFS, mecanismo para impedir conexões `sqlite3` não instrumentadas e bypasses, versões SQLite/APS W/Windows/Linux, objetos auxiliares, limites de resource. Uma conexão alternativa funcionando sem gate é **FAIL**.
- **G6 / evidência:** testes RED anteriores/novos, asserts e exit codes, CI real Ubuntu+Windows, 5 acceptance RED externos intactos e Quality/Security canônicas; SHA exato dos testes. Nunca converter falhas em skip/xfail ou aceitar só marker stdout.

**Não declarar P0-5/6 fechado** somente porque hooks viram `xRead/xWrite`: a proteção deve garantir invariantes e integrar os fluxos operacionais; a custódia/antirollback tem gates independentes.

## 6. Gates humanos para P0-1/2/3/4 (não executados)
- **P0-1:** identidade HUMAN_OWNER autenticada fora do chamador e vinculada à chave, escopo, papel, perda/rotação; decisão humana sobre provedor e forma de bootstrap.
- **P0-2:** origem independente da raiz de confiança + rotação, revogação, recibo do efeito com vínculo a intenção/nonce/seq/fornecedor/frescor; não existe provedor real contratado.
- **P0-3:** identidade do evento de negócio **autêntica**, reserva de primeira tentativa durável/global antes de `send`; idempotência por evento original, não ID de requisição autoafirmado. `UNCERTAIN` não libera `RETRY`.
- **P0-4:** estado/contador monotônico fora do domínio de restauração simultânea do host; fail-closed se testemunha offline, H0 após perda total sem auto-bootstrap.
- **Custos:** nenhuma estimativa de serviço autenticador/custódio foi obtida nesta análise. **Não contratar nem prometer caber no teto** sem orçamento real e aprovação prévia.

## 7. Nota de supply chain
Os 43 achados do audit A184 são de versões vulneráveis **presentes no stack A184**, enquanto existem propostas Draft independentes #1445 e #1448 (Streamlit, Pillow 13, pypdf atualizado). NÃO transferir o selo de `pip-audit=0` dessas propostas para A184 sem rebase/testes de compatibilidade completos e resolução de empilhamento. A185 desta PR é **somente documentação**, sem novo pacote `apsw`, sem atualizar `requirements.txt`.

## 8. Estado para aceite e ordem seguinte
- Esta ADR é um **preflight de arquitetura**: não prova teste de VFS, alteração de CI, correção funcional, compilação nativa nem homologação. PR Draft separada e baseada em A184, sem main.
- Codex A185 deve usar esta hipótese como material a questionar, **não** como garantia. Ordem de entrega: (1) testar G1/2 com VFS do motor; (2) G3/4 e call-site sweep; (3) comparar A/B/C com resultados; (4) CI real; (5) atualizar matriz sem inventar autoridade externa.
- Status: **0/6 P0, HARD NO-GO, ZERO_AUTO_RESEND. Sem merge, deploy, Worker, broker, credenciais, contratação, APIs pagas ou efeitos externos.**
