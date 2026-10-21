# AION P0/H0 — stale adapter readback e negação pré-fornecedor (LAB 21/10/2026)

**HARD NO-GO, 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND; sem merge/deploy/credenciais/gastos.**

## Linha de base e causa raiz

Na Quality canônica da PR #1391, commit `84c0d74b3d2f3ef74876eab2c19da361c6347abf`, execução https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39597659192, ocorreram **6.895 testes: 50 FAIL + 22 ERROR**. Dos 22 erros, 13 são Outbox e 9 Saga. Os casos selecionados deste bloco são **6 métodos e 7 ocorrências** (um método `test_adapter_rejection_boolean_does_not_release_aggregate` tem dois subtests).

O produto **corretamente bloqueia** `dispatch_claimed` e `reconcile` antes de acessar callbacks de adaptadores sem emissor e produtor independente autenticados. Os contratos legados de concorrência usavam callbacks `send/reconcile` para gerar corridas de estado que, neste modo NO-GO, devem ser inalcançáveis.

## Seis métodos revisados: não fingir prova nem reabrir efeito

1. `OutboxStaleStateBlockCASP0Tests.test_reconcile_late_block_cannot_clobber_confirmation`: primeira tentativa é bloqueada e sem send; uma linha SENT criada por SQL *somente de teste* recusa readback; transição posterior para CONFIRMED usa outra fixture SQL, nunca atestado do fornecedor.
2. `OutboxReconcileStaleRetryCASP0Tests.test_stale_absence_must_not_reopen_confirmed_effect`: o teste proíbe até ler a propriedade maliciosa de `adapter.reconcile`; snapshot CONFIRMED sintético não admite nova conciliação.
3. `OutboxReconcileStaleRetryCASP0Tests.test_stale_absence_cannot_reopen_revoked_state`: o valor REVOGADO de uma fixture nunca volta a RETRY por observação tardia.
4. `OutboxReconcileStaleRetryCASP0Tests.test_unverified_absence_cannot_invoke_authorize_or_reopen_retry`: adapter e authorize NÃO executam; nenhuma segunda claim, estado SENT sintético continua pendente de prova.
5. `OutboxUnverifiedAdapterResultP0Tests.test_adapter_rejection_boolean_does_not_release_aggregate`: tanto `retryable=True` quanto `False` devem ser barrados antes de chamada, mantendo `BLOCKED_PRODUCER` não-terminal e o segundo item em `PENDING`.
6. `OutboxUnverifiedAdapterResultP0Tests.test_false_authoritative_absence_remains_quarantined`: um retorno de suposta ausência é inacessível; `UNCERTAIN` histórico sintético não vira confirmação de não efeito nem autorização de reenvio.

**Todos os identificadores canônicos, classes e quantidade de testes existentes foram preservados.** Os dois inventários de falhas e a matriz de coordenadas originais continuam verificando os blobs Git históricos e o AST atual. Nenhum skip/xfail. Nenhum método de produto ou banco foi modificado.

### Limitação de cobertura essencial

Os resultados provam somente **denial correctness** (proibição de envio/readback no estado não homologado) e parte da imutabilidade local de estados terminais. A fixture SQL que cria `SENT`/`CONFIRMED` e uma linha `action_effects` **não é** um efeito real, recibo do emissor ou homologação do CAS sob corrida real. Os antigos testes de corrida positiva deixam de exercitar callbacks reais por decisão de segurança. Exigir testes positivos separados após matrícula independente, reserva off-host atômica, vínculo causal, fonte monotônica e fornecedor com semântica de deduplicação/fence verificável.

### Evidência exigida para fechamento do bloco

- GitHub Actions isolado Ubuntu e Windows: seis métodos migrados, cinco controles adicionais de hard-stop, 12 verificações do inventário de 85 ocorrências, 10 testes da matriz original de 32 erros e 64 de causalidade H0.
- Quality completa sem filtro/waiver no SHA final; comparar FAIL/ERROR **identificador por identificador** com a linha de base PR #1391.
- Não declarar redução nem mudança de segurança real antes da execução. A principal limitação — prova independente do resultado da primeira tentativa após restauração de SQLite — continua aberta.
