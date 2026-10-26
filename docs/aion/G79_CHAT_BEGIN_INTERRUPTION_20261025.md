# AtlasQuant / AION G79 — BEGIN interrompido, quarentena local

**Base isolada:** G78 `003b5e6a22e712e46235fe303e4c75b958f4b9f8`. **Estado:** candidato LAB Draft, nenhum merge/deploy/Worker/SEND, zero custo de provedor. **P0 0/6 homologadas, HARD NO-GO e ZERO_AUTO_RESEND.**

## Descoberta verificável

`aion_chat/store.py::_begin_or_quarantine` chamava `self.db.execute("BEGIN IMMEDIATE")` sob `except Exception`. Assim, `KeyboardInterrupt` ou `SystemExit`, lançados antes/depois de o SQLite ter adquirido a transação, escapavam sem quarentena. Mesmo um `OSError` comum podia ser substituído por `SystemExit` secundário durante `close`. A operação de criação de conversa alcança essa rotina; não é um caminho teórico de arquivo morto.

## Prova negativa RED antes do patch

Codex `01a17606-5aa9-7c43-9739-ba0ec73d8e1f` escreveu primeiro `labs/a190/test_g79_chat_begin_interrupt_lab.py`, sem alterar produção e sem executar SQLite dentro de seu sandbox Windows com problemas de acesso temporário.

**Execução independente no Windows autorizado, ainda em G78 original:**

```text
py -B -m unittest -v labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt
Ran 8 tests
FAILED (failures=6)
exit 1
```

Quatro interrupções antes/depois de BEGIN deixavam `close_count=0`; duas falhas de fechamento secundárias mascaravam a identidade da exceção original; dois controles OSError passaram. Sem erros de fixture. Nenhum HTTP, credencial, provedor ou operação financeira foi utilizado.

## Patch e prova GREEN local

Somente `_begin_or_quarantine` passou a capturar `BaseException` na fronteira ambígua de BEGIN, executando quarentena local mesmo se a exceção for `KeyboardInterrupt/SystemExit`, e preservando a exceção primária se a quarentena lançar outra `BaseException`. Mantida anotação `AION_CHAT_BEGIN_OUTCOME_UNCERTAIN_STORE_QUARANTINED`. Não há reenvio, rollback de compensação, segunda tentativa, nem mudança em `COMMIT` ou `ROLLBACK`.

```text
py -B -m unittest -q labs.a190.test_g79_chat_begin_interrupt_lab.G79ChatBeginInterrupt labs.a190.test_g78_chat_commit_interrupt_lab.G78ChatCommitInterrupt labs.a190.test_g33_chat_ambiguous_commit_lab labs.a190.test_g32_chat_store_rollback_quarantine_lab test_atlasquant_aion_first_attempt_witness_a180_lab labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 73 tests
OK
exit 0

git diff --check
exit 0
```

Os testes verificam uma tentativa de BEGIN, fechamento/quarentena, identidade da interrupção propagada, conexão inutilizada para novas escritas, ausência de rollback/retry, banco recém-reaberto e ausência de conversa registrada na transação interrompida.

## Limites de homologação

Este é um teste sintético in-processo em Windows, e não prova recuperação sob desligamento físico, SQLite nativo/VFS real da instalação final, testemunha externa independente, recibos autenticados ou monotonicidade após restauração do host e da custódia. A autoridade da primeira tentativa continua indisponível. A análise separada das interrupções de `ROLLBACK` ainda é necessária.

A execução do mesmo SHA no CI Windows e Ubuntu deverá ser lida antes de declarar sucesso multiplataforma. Os gates A184 externos e canônicos permanecem independentes e bloqueadores.

## Revisão independente do Codex

Sessão read-only `01a17608-c74f-7ef3-868e-fd334d199731`: nenhum defeito alto ou médio encontrado no trecho inspecionado; diferenças de produção com a cópia local G78 limitadas ao handler de BEGIN. Lacunas de cobertura **não homologadas**: estado interno não aferido durante `close`, liberação física em interrupção anterior ao fechamento nativo, outros pontos de gravação além de `create_conversation`, interrupções assíncronas reais e exceção customizada cujo `add_note()` também falhe. A inspeção não reexecutou testes nem autenticou de modo independente o SHA Git; ambos exigem evidência separada. G79 permanece contenção local, não custódia H0 externa.
