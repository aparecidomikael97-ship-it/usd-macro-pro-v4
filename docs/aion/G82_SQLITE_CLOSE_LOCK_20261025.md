# AION P0 G82 — falha de close e trava SQLite (LAB)

**Base isolada:** G81 `eed76454512e900dc48081e52c3ad966b074770a`. **Escopo:** exclusivamente o método `SQLiteChatStore.close()` e novo módulo de testes sintéticos. **Estado: Draft LAB · P0 0/6 homologadas · HARD NO-GO · ZERO_AUTO_RESEND.** Sem merge/deploy/Worker/SEND.

## Defeito de reutilização após falha de fechamento

O método `close()` de `aion_chat/store.py` só desanexava `self.db` depois de chamar `db.close()`. Se o fechamento lançasse `KeyboardInterrupt`, `SystemExit` ou `OSError`, o objeto permanecia aparentemente saudável e com conexão anexada, podendo aceitar nova gravação apesar da tentativa de encerramento.

## Testes adversariais escritos antes do patch

Codex, sessão `01a17636-8421-7513-ae84-f16f28eab15e`, preparou primeiro `labs/a190/test_g82_close_failure_reuse_lock_lab.py`, sem modificar produção nem executar testes no sandbox Windows restrito.

Windows host, G81 original:

```text
py -B -m unittest -v labs.a190.test_g82_close_failure_reuse_lock_lab
Ran 8 tests
FAILED (failures=11); 5 métodos com falhas, 3 métodos PASS
exit 1
```

Cinco casos envolvendo falha antes/depois do `close` nativo demonstraram violações de desanexação, saúde FAILED e proibição de reutilização. Um controle exercitou `close()` normal e idempotente; dois casos caracterizaram uma trava persistente quando a quarentena é atingida, mas o fechamento do handle físico falha *antes* da chamada nativa.

## Correção mínima, GREEN local

Codex, sessão `01a17638-1017-7b73-a0cf-a5ad15a388cf`, modificou somente `SQLiteChatStore.close()`: guarda `connection` local, desanexa `self.db` **antes** de chamar `connection.close()`; em qualquer `BaseException` do fechamento, marca `FAILED`, razão estável `CLOSE_OUTCOME_UNCERTAIN`, e relança a exceção original. Não tenta rollback, reenvio ou nova tentativa de fechamento. O fechamento normal segue idempotente.

```text
py -B -m unittest -q labs.a190.test_g82_close_failure_reuse_lock_lab labs.a190.test_g81_chat_body_interrupt_lab labs.a190.test_g80_chat_rollback_interrupt_lab.G80ChatRollbackInterrupt labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 101 tests
OK
exit 0
git diff --check: exit 0
```

## Risco restante: bloqueio de outros escritores

A quarentena desanexa o banco e barra reutilização, mas **não garante a liberação física do handle** quando `close()` falha antes de executar o fechamento real. Em G82, outra conexão observa SQLite busy/locked durante o período em que o fixture retém a transação e consegue iniciar uma nova escrita **após** a liberação explícita na limpeza dos testes. O AION não pode declarar o banco recuperado nesse estado. Este risco não está homologado ou resolvido com um novo mecanismo de custódia.

**Limites:** nenhuma prova de desligamento físico de energia, reinício inesperado, testemunha off-host, recibo autenticado do provedor, identidade humana externa, antirollback independente, ou SQLite nativo da plataforma final. Revisões canônicas da A184 permanecem independentes. A CI do SHA G82 só pode ser declarada verde após ler os logs em Ubuntu/Windows.


## Revisão independente e limitações adicionais

Codex read-only sessão `01a17639-4f5e-74e1-90dc-b93b721e3b9d`: **0 findings altos, 0 médios, 1 baixo** para o escopo de produção avaliado. Achado de cobertura corrigido no próprio teste: agora comprova que `self.db` já estava desanexado na entrada do `close()` e que `_health_state` é `FAILED` após falha. O host reexecutou **101/101** testes, sem falhas.

**Consequência operacional separada e ainda pendente:** no adaptador de sessão local, uma chamada `holder.close()` que propague uma exceção pode impedir a retirada do holder de `session_state`. O holder remanescente não deve conseguir escrever porque o store está desanexado; mas a remoção da sessão e a liberação de um handle físico retido não foram homologadas. Essa integração não foi alterada na G82.

Caracterização de trava retida: o controle `BEGIN IMMEDIATE` de uma segunda conexão falha com busy/locked **antes** da limpeza do fixture; o bloqueio desaparece **depois** que o próprio fixture fecha o handle. Não atribuir a liberação ao código da G82, não atribuir custódia independente, não converter P0 em PASS.
