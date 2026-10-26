# AION G83 — isolamento de cleanup de inicialização SQLite interrompido (LAB)

**Base exata:** G82 `e384301e95e0231b352a72acfba713ac911e7c49`. **Status: Draft LAB somente. P0=0/6 homologadas, HARD NO-GO, ZERO_AUTO_RESEND; sem merge/deploy/Worker/SEND.**

## Defeito observado

Em `aion_chat/store.py::SQLiteChatStore.__init__`, o bloco que trata erro de inicialização (sqlite3.DatabaseError/OSError/StorageUnavailableError) tentava fechar `self.db` e capturava apenas `Exception`. Se o `close` levantasse `KeyboardInterrupt` ou `SystemExit` ANTES/DEPOIS de alcançar o fechamento nativo, a segunda interrupção substituía o erro original de startup, podia pular `self.db=None` e até aparentar saúde HEALTHY. Esse caminho é diferente de `SQLiteChatStore.close` que foi corrigido na G82.

## Testes-first RED real (antes da correção)

Codex `01a1764a-aa8b-7372-807d-cd00308728a8` criou `labs/a190/test_g83_constructor_cleanup_interruption_lab.py`, mantendo a produção G82 intacta e sem rodar SQLite no sandbox Windows. O teste usa uma fábrica de conexão sintética que executa o schema real, obtém `BEGIN IMMEDIATE`, injeta o erro OSError original de startup e depois intercepta o fechamento. Na variante pré-native-close, o segundo escritor com timeout=0 comprova o lock retido **antes da limpeza do fixture**, que só depois fecha o handle bruto. Na variante pós-native-close comprova nova escrita possível. Há dois controles.

Executado de forma independente no Windows autorizado:

```text
py -B -m unittest -v labs.a190.test_g83_constructor_cleanup_interruption_lab
Ran 6 tests
FAILED (failures=22)  # assertivas/subtestes, não 22 testes distintos
exit 1
```

Nenhum ERROR de fixture. Em quatro casos, a exceção de fechamento mascarou a falha de inicialização, o objeto ficou anexado e a falha pré-fechamento permitiu tentar outra operação apesar da transação ainda ativa.

## Correção mínima e GREEN independente

Codex `01a1764c-715f-72f2-8374-2a785d07f5a9` alterou **somente uma linha** do handler de limpeza de construtor: `except Exception` para `except BaseException`, exclusivamente quando já houve erro de inicialização tratado, mantendo o fechamento único, `self.db=None`, estado FAILED e propagação de `StorageUnavailableError` original ou derivada de OSError conforme a semântica anterior. Não há segundo fechamento, rollback ou reenvio.

```text
py -B -m unittest -q labs.a190.test_g83_constructor_cleanup_interruption_lab labs.a190.test_g82_close_failure_lock_lab labs.a190.test_g81_chat_body_interrupt_lab labs.a190.test_g80_chat_rollback_interrupt_lab.G80ChatRollbackInterrupt labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 105 tests
OK
exit 0
git diff --check: exit 0
```

## Limites e pendências

Esta correção trata **interrupção durante limpeza de startup que já falhou com uma exceção conhecida**. Não afirma que `KeyboardInterrupt/SystemExit` levantados diretamente no `executescript` do construtor sejam tratados. Não garante liberar o handle nativo se seu `close` interrompe antes da operação física; um writer lock retido pode exigir encerramento do processo/handle. Não prova energia, reinício real H0, testemunha externa monotônica/antirollback, autenticação de identidade e recibos externos, ou compatibilidade VFS SQLite nativa. A184 canônica e seis P0 continuam gates independentes.

Conferência Ubuntu/Windows pela CI só será considerada concluída quando jobs e logs do SHA específico forem lidos. Nenhum merge/deploy/Worker/ordem real foi autorizado.

## Revisão independente e próximo bloqueio

Codex read-only sessão `01a1764d-7ecd-7922-8c03-fdb0e7d93c31` revisou a diferença contra o SHA G82 e não encontrou defeito alto no handler modificado. **Lacuna MÉDIA separada e não corrigida:** uma `KeyboardInterrupt`/`SystemExit` disparada **diretamente durante a inicialização** (`executescript`, antes de o handler externo receber `Exception`) ainda pode ignorar limpeza, desanexação e estado FAILED. Essa fronteira exige outro RED em LAB, sem supor liberação de handle nativo. **Lacuna BAIXA de cobertura:** testes G83 ainda não injetam como erro primário um `StorageUnavailableError` já instanciado, embora o ramo de `raise` o preserve por inspeção; nem contam commits de cleanup, que não aparecem no código de cleanup. Essas limitações não autorizam homologar P0/H0.
