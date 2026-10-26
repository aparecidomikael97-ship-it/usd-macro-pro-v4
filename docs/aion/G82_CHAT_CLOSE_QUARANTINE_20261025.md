# AION P0 G82 — fechamento SQLite de resultado incerto, sem reutilização (LAB)

**Base G81:** `eed76454512e900dc48081e52c3ad966b074770a`. **Estado: DRAFT LAB, zero merge/deploy/Worker/SEND. 0/6 P0 HOMOLOGADAS, HARD NO-GO, ZERO_AUTO_RESEND.**

## Defeito real e limite separado

Em `aion_chat/store.py::SQLiteChatStore.close`, a antiga implementação somente definia `self.db=None` depois do retorno normal do fechamento nativo. Uma interrupção `KeyboardInterrupt` ou `SystemExit` antes/depois da chamada real `close` mantinha o objeto `db` anexado; quando a interrupção antecedia o fechamento nativo, o armazenamento podia continuar indicando saúde HEALTHY e tentar nova escrita apesar do estado incerto.

A auditoria anterior do Codex `01a17633-4c64-7cb1-b0be-266687fd2efb` identificou ainda o limite diferente de `quarantine_failed_transaction`: desanexar a conexão e negar novos envios **não garante** a liberação do handle se o fechamento é interrompido antes do `raw.close`. Aquele writer lock pode continuar bloqueando outros escritores do mesmo SQLite. Isso é uma limitação operacional real, não evidência de operação externa repetida.

## Prova RED, antes de qualquer patch na produção

Codex `01a1763f-2389-7e80-94f3-180b3b108b78` criou primeiro `labs/a190/test_g82_close_failure_lock_lab.py` com seis testes sintéticos no worktree separado. Execução independente no Windows autorizado, com código original G81:

```text
py -B -m unittest -v labs.a190.test_g82_close_failure_lock_lab
Ran 6 tests in 0.259s
FAILED (failures=10) [subtestes e assertivas]
exit 1
```

Sem erros de fixture. Falharam as asserções sobre `db=None`, FAILED, bloqueio de reutilização e número de tentativas de fechamento em interrupções antes/depois do fechamento nativo. Controle de `close` normal e reprodução do writer lock retido após quarentena G81 passaram no baseline. O teste de lock usa `BEGIN IMMEDIATE` com `timeout=0` em segunda conexão **antes** da limpeza e constata que o bloqueio some somente após fechamento do raw no fixture. Nenhuma rede, credencial ou efeito real.

## Correção estrita e GREEN local

Codex `01a17641-2c50-7902-974a-b529c845355e` alterou **somente** `SQLiteChatStore.close`: se a tentativa de fechamento levantar `BaseException`, desanexa `db`, marca `FAILED` e `CLOSE_OUTCOME_UNCERTAIN_NO_REUSE`, e repropraga a exceção original. Não repete `close`, não faz `rollback`, `commit` nem reenvio. Caminho normal mantém fechamento único/idempotente. Este patch **não resolve** handle nativo retido quando o fechamento não executa; não pode afirmar a liberação física.

```text
py -B -m unittest -q labs.a190.test_g82_close_failure_lock_lab labs.a190.test_g81_chat_body_interrupt_lab labs.a190.test_g80_chat_rollback_interrupt_lab.G80ChatRollbackInterrupt labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 99 tests in 6.308s
OK
exit 0
git diff --check: exit 0
```

## Condições externas ainda pendentes

Esta proteção é local, dentro de um processo vivo. NÃO comprova disponibilidade após queda de energia/processo, ausência de locks órfãos em outros handles, SQLite nativo/driver no ambiente final, testemunha externa linearizável, monotonicidade após rollback H0, autenticação de recibos, identidade HUMAN_OWNER nem exatamente uma execução financeira. Os seis P0 continuam abertos. Só declarar resultado CI Windows/Ubuntu após verificar jobs e logs do SHA exato; falhas do A184 e suites canônicas permanecem gates separados. Nenhum merge/deploy/Worker/ordem real foi autorizado.

## Revisão independente e pendências

Codex read-only `01a17642-3256-7da0-929c-1f486b58accb` não encontrou defeito bloqueante na correção estrita de `SQLiteChatStore.close()`. Identificou: **P2** caminho adjacente de limpeza de conexão no construtor (`aion_chat/store.py`, aproximadamente linha 430) que chama `self.db.close()` diretamente e captura só `Exception`, sem garantir desanexação após `KeyboardInterrupt/SystemExit`; não foi alterado nesta PR. **P3** a idempotência depois de close malsucedido não era testada; o teste G82 foi ampliado para chamar `close()` novamente, exigir contagem inalterada e, quando o handle físico não fechou, confirmar writer lock ainda retido. Reexecução host Windows ampliada: `Ran 99 tests`, `OK`, saída 0, `git diff --check` saída 0.

**Próximo LAB possível:** tratar separadamente o caminho do construtor com RED válido antes de tocar a produção. G82 não garante a liberação de um handle nativo que falhou antes de `raw.close()` nem homologação P0/H0.
