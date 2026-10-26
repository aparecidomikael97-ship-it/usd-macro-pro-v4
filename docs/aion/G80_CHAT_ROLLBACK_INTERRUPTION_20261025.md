# AION G80 — interrupção no rollback do SQLiteChatStore

**Baseline isolada:** G79 `21bde47cec7e60f26a762d03829090eb8af24060`. **Segurança:** apenas Draft LAB, sem merge, deploy, Worker, SEND real ou gasto novo. **P0=0/6 homologadas; HARD NO-GO; ZERO_AUTO_RESEND.**

## Falha de tratamento de erro

Ao ocorrer falha durante o corpo de uma transação, `aion_chat/store.py::_rollback_or_quarantine` preservava o erro original apenas quando o rollback falhava com `Exception`. Uma interrupção com `KeyboardInterrupt` ou `SystemExit` escapava e podia deixar a conexão sem quarentena, até mesmo quando SQLite já executara o rollback. Uma falha secundária em `close()` podia substituir o erro inicial.

A auditoria Codex read-only `01a1760c-563c-7cd1-975f-849e87b0b37d` identificou este contrato e delimitou o corpo da transação como investigação separada.

## RED verificado antes da alteração

Codex `01a1760e-0537-78c2-8e93-ddedf6803824` criou primeiro `labs/a190/test_g80_chat_rollback_interrupt_lab.py`; não executou testes no sandbox Windows. Execução independente no Windows conectado, antes de mudar produção:

```text
py -B -m unittest -v labs.a190.test_g80_chat_rollback_interrupt_lab.G80ChatRollbackInterrupt
Ran 6 tests
FAILED (failures=5)
exit 1
```

Os quatro testes com rollback interrompido antes/depois da chamada real retornaram `KeyboardInterrupt` ou `SystemExit`, em vez da instância original `RuntimeError` do INSERT. O caso de erro secundário ao fechar também mascarou o erro original. Controle OSError passou. Nenhum erro de preparação.

## Correção e GREEN local

Codex `01a1760f-5443-79b1-b933-13fdc5f64152` alterou somente `_rollback_or_quarantine`: captura `BaseException` no limite do rollback, tenta quarentena sem substituir o erro original por falha secundária de `close`, mantém `raise primary_error from rollback_error` e anotação existente. Nenhum retry, requeue, segundo rollback ou autorização de envio.

```text
py -B -m unittest -q labs.a190.test_g80_chat_rollback_interrupt_lab.G80ChatRollbackInterrupt labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 79 tests
OK
exit 0
git diff --check: exit 0
```

Provas sintéticas: instância da exceção original, causa vinculada à interrupção do rollback, uma tentativa, conexão isolada e estado FAILED, novas escritas negadas e consulta ao banco reaberto sem inserir conversa não confirmada.

## Limites

Isto não é prova de energia física, disponibilidade H0 fora do host, monotonicidade antirrollback, autenticação externa de identidade/recibos ou homologação SQLite/VFS na plataforma alvo. O `except Exception` no *corpo* da transação ainda precisa de trabalho separado; esta PR não amplia essa captura. Um rollback concluído localmente não concede direito de reexecutar operação incerta. A suíte A184 permanece independente. CI Ubuntu/Windows do SHA exato deverá ser conferida antes de qualquer afirmação de sucesso multiplataforma.

## Revisão independente pós-patch

Codex read-only, sessão `01a17610-39c8-78b2-9a5c-d980a66cd03f`: nenhum defeito alto/médio encontrado no handler G80 inspecionado. A causa da exceção original é preservada, a conexão desanexada antes do fechamento e nenhuma nova tentativa é autorizada. **Limites de cobertura não resolvidos:** o teste confere `db=None` depois do `close`, mas não no início dele; o cenário de falha de `close` é injetado depois de fechar fisicamente o banco. **Defeito distinto, não corrigido na G80:** o `except Exception` no corpo de `_managed_write_transaction` ainda não contempla `KeyboardInterrupt/SystemExit`, podendo deixar transação ativa; requer RED separado. Não classificar essa revisão de código como prova de custódia externa ou de power-loss.
