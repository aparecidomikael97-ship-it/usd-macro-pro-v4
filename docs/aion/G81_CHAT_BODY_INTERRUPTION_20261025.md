# AION P0 G81 — contenção de interrupção durante corpo de transação SQLite (LAB)

**Base imutável:** G80 `0a61fc2ff774a4e871a3801dc86209c76aa94fdb`. **Escopo de produção:** somente `aion_chat/store.py` em dois handlers de corpo de escrita. **HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas.** Sem merge, deploy, Worker, provedor SEND ou finanças.

## Dois caminhos operacionais encontrados

`SQLiteChatStore._managed_write_transaction()` (por exemplo, `create_conversation`) e `SQLiteChatStore.append_message()` usavam `except Exception` para falhas durante a transação. Uma interrupção não convencional como `KeyboardInterrupt` ou `SystemExit` escapava sem rollback explícito e sem desanexar a conexão ainda aberta. Isso é diferente das correções G77–80 sobre BEGIN, COMMIT e ROLLBACK. O estado local podia ser reutilizado indevidamente após interrupção do corpo.

## Primeiro RED, antes do patch

Codex sessão `01a17615-9c30-7a73-981b-316175d2734c` criou exclusivamente `labs/a190/test_g81_chat_body_interrupt_lab.py`, com dez testes sintéticos e nenhuma mudança de produção. Não executou SQLite dentro de seu sandbox Windows.

Execução separada no host Windows, antes da correção, sobre G80 original:

```text
py -B -m unittest -v labs.a190.test_g81_chat_body_interrupt_lab
Ran 10 tests in 0.400s
FAILED (failures=9)
exit 1
```

**9 FAIL de assertiva, 1 PASS de controle OSError, 0 ERROR de fixture.** Testes com `KeyboardInterrupt`/`SystemExit` antes e depois de INSERT de conversa/mensagem e depois de atualização posterior à mensagem observavam `close_count=0` em vez de quarentena. Tudo local: sem HTTP, API ou dados reais.

## Patch mínimo e validação GREEN

Codex sessão `01a17617-b3e6-75e3-bc11-05a60c887daa` acrescentou somente `except BaseException` separado, após o handler convencional `except Exception`, em cada um dos dois corpos. Esse ramo **não tenta rollback/retry/requeue/commit**: apenas chama a quarentena local, que desanexa a conexão e marca estado FAILED antes do close. Se close lançar uma exceção secundária, a interrupção original continua sendo propagada. Todos os tratamentos anteriores de `Exception` e `sqlite3.DatabaseError` permanecem.

Execução independente no host Windows, após patch:

```text
py -B -m unittest -q labs.a190.test_g81_chat_body_interrupt_lab labs.a190.test_g80_chat_rollback_interrupt_lab.G80ChatRollbackInterrupt labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 93 tests in 3.220s
OK
exit 0

git diff --check: exit 0
```

## Limitações explícitas

Os cenários usam proxies de SQLite e dados sintéticos. Eles não reproduzem corte físico de energia, encerramento do processo antes de executar o handler, falha no fechamento físico antes da liberação do handle, antirollback fora da máquina, testemunha externa independente, identidade HUMAN_OWNER real, recibos do provedor ou comportamentos reais da integração. Este patch é de contenção local, **não homologação das P0 3/4/5/6**, nem certificação canônica Security/Quality. A verificação no CI do SHA específico só pode ser declarada após checar logs dos jobs Ubuntu e Windows.

## Revisao independente e cobertura adicional
Codex read-only sessao 01a17618-981f-78d0-8d1e-70b70aee6e55 nao detectou defeito alto no patch, mas apontou lacuna media de cobertura quanto a falha secundaria do fechamento fisico. Codex 01a1761a-870a-7bd3-a01b-08530df54d8e alterou exclusivamente o fixture de testes, incluindo quatro casos novos. O teste agora verifica se a conexao ja esta desanexada e FAILED no instante em que close comeca; tambem diferencia excecao apos fechar o handle (liberacao constatada) de excecao antes de fechar (handle ainda retido; SEM garantia de liberacao). Novo host Windows: Ran 93 tests, OK, exit 0. Limites externos e de processo seguem pendentes.
