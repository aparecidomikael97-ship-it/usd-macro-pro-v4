# AION G77 — interrupção de COMMIT pré-testemunha: RED → GREEN em LAB

**Snapshot de base:** G76 `651c58848ec9a50102aa8994fbb67c5eac9b3f1c`. **Estado:** Draft LAB, sem merge, sem deploy, sem Worker e sem SEND. **P0 homologadas: 0/6; HARD NO-GO, ZERO_AUTO_RESEND.**

## Defeito localizado

Em `atlasquant_aion_execution_outbox.py::_commit_or_quarantine`, um `except Exception` não capturava `KeyboardInterrupt` nem `SystemExit` após um COMMIT de SQLite cujo ACK se perdeu. Assim, a conexão local podia permanecer aberta sem quarentena. O risco é especialmente relevante na persistência de `UNCERTAIN` antes de consultar a testemunha; a auditoria **não provou** duplicação real nem disponibilidade H0 fora do host.

A falha foi detectada pela auditoria de código Codex read-only `01a175f1-07eb-76a3-8367-573495321ee0`. Ela **não executou testes**.

## Prova negativa válida antes da correção

Codex workspace-write `01a175f3-5274-7ae1-b6fa-f1cc82525787` criou sete casos no arquivo `labs/a190/test_g77_commit_interrupt_quarantine_lab.py` e não alterou a produção antes do RED. O sandbox de Codex para Windows não podia abrir arquivos SQLite temporários (7 testes, 14 erros de fixture), então **esses erros não foram usados como evidência RED**.

Uma execução independente posterior no Windows pelo terminal remoto autorizado, **fora do sandbox do Codex**, com a produção original, reproduziu:

```text
py -B -m unittest -v labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine
Ran 7 tests
FAILED (failures=5)
exit code 1
```

Os cinco FAIL ocorreram ao verificar `proxy.closes == 1`, com valor real zero: `KeyboardInterrupt` e `SystemExit`, antes e depois do COMMIT, mais interrupção secundária durante `close`. Os dois casos `OSError` existentes passaram. **Nenhum ERROR** ocorreu nessa execução válida.

## Correção mínima e resultados após patch

A alteração na produção fica confinada a `_commit_or_quarantine`: `except BaseException` no limite ambíguo de COMMIT; tentativa de quarentena do storage; `self.db = None` mesmo se o fechamento gerar uma segunda `BaseException`; preservação da exceção original e anotação `AION_OUTBOX_COMMIT_OUTCOME_UNCERTAIN_NO_AUTO_RESEND`. **Sem rollback automático, requeue, reenvio ou ampliação das permissões de callbacks**.

Execução independente fora do Codex sandbox:

```text
py -B -m unittest -q labs.a190.test_g77_commit_interrupt_quarantine_lab.G77CommitInterruptQuarantine test_atlasquant_aion_first_attempt_witness_a180_lab test_atlasquant_aion_execution_outbox test_atlasquant_aion_outbox_uncertain_retry_a176_lab test_atlasquant_aion_outbox_receipt_admission_a177_lab
Ran 52 tests
OK
exit code 0
git diff --check
exit code 0
```

Os testes verificam: mesma instância da exceção lançada; ausência de callback de testemunha e de adapter SEND; ausência de rollback; conexão fechada e handles detached; saúde do storage em falha; reabertura com `UNCERTAIN` persistido após COMMIT e sem novo claim mesmo após lease expirado. Também preservam o caso em que COMMIT não ocorre.

## Limites e próximos critérios

Esta é **proteção local de tratamento de exceções**, não teste de interrupção de energia real, sincronização entre máquinas, autenticação independente de testemunha, prova assinada por provedor, idempotência por evento empresarial original, antirollback externo nem SQLite/VFS homologado. A G75 segue proibindo envio externo real. Testes sintéticos aprovados não autorizam operar com clientes ou dinheiro.

Validação Ubuntu/Windows na CI do commit G77 só será considerada concluída após verificar os jobs e os logs exatos. As seis P0 continuam abertas, sem merge, deploy ou Worker ativado.
