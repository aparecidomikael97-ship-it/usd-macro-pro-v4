# AION P0 — staging Saga + Outbox: readback sob lock e CAS de escopo (LAB)

**Data 21/10/2026 · somente PR Draft LAB. HARD NO-GO / Worker OFF / ZERO_AUTO_RESEND / 0/6 P0 homologados.**

## Risco analisado

O método real `ExecutionSagaCoordinator.enqueue_next` começa `BEGIN IMMEDIATE`, lê a Saga, verifica `integrity_report`, escolhe a etapa e chama `ExecutionOutbox.enqueue`, que insere uma decisão e uma linha de Outbox no mesmo SQLite por SAVEPOINT. O método original, **após** a chamada a Outbox, gravava:

```sql
UPDATE aion_execution_saga_steps SET state='ENQUEUED',outbox_key=? WHERE saga_id=? AND step_key=?;
UPDATE aion_execution_sagas SET state='RUNNING',updated_at=? WHERE saga_id=?;
```

Esses dois UPDATEs não conferiam que exatamente uma linha foi atingida, não verificavam `owner/tenant/workspace` dentro do SQL e não revalidavam o snapshot após a inserção no Outbox. Um gatilho SQLite preexistente/hostil em `AFTER INSERT ON action_outbox` pode mudar `step_key`, `state`, `payload`, `owner/tenant` ou o estado/digest da Saga dentro da própria transação. Com `step_key` alterado, o UPDATE da etapa pode afetar 0 linhas sem gerar erro, embora o Outbox seja inserido e o pai seja marcado `RUNNING`. A cadeia final de eventos não prova uma relação válida com a etapa alterada. É um caso de corrupção local ou código/trigger com privilégios no banco, **não** evidência de uma vulnerabilidade remota e **não** uma prova de rollback físico.

### Bateria RED-first antes do patch

`tests/test_aion_p0_saga_atomic_scoped_stage_cas_lab.py` contém 9 cenários com `SQLiteChatStore`, `ExecutionOutbox`, `CumulativeAuthorityBudget` e `ExecutionSagaCoordinator` reais em banco temporário. Os gatilhos de teste mudam:
- `step_key` do primeiro passo durante o enfileiramento;
- `state` da etapa para `BLOCKED_PRODUCER`;
- `payload` da etapa;
- `state` do pai para `COMPLETED`;
- `tenant` da Saga;
- `plan_digest` da Saga;
- falha SQL explícita;
- e verificam o fluxo normal sem envio.

A pré-correção ficou no commit `867735f500f0d5a26a4f7c898d126a7b94b84cb9`, workflow [#39617618624](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39617618624). A decisão final deve registrar **o resultado real** (não supor RED nem GREEN antes da CI).

## Correção proposta no código real

Após `outbox.enqueue`, ainda dentro da transação IMMEDIATE:

1. Refaz `get` da Saga e `integrity_report`. Qualquer falta de pai, alteração da projeção, mudança do plano ou inconsistência local bloqueia com `PermissionError("SAGA_STAGE_SNAPSHOT_STALE")`.
2. Atualiza a etapa com `WHERE saga_id/step_key/state`, sujeito a `EXISTS` sobre a Saga pai e sua identidade `owner/tenant/workspace`, estado anterior e `plan_digest`. Se `rowcount != 1`, bloqueia.
3. Atualiza a Saga pai com `WHERE saga_id/owner/tenant/workspace/state/plan_digest`, conferindo `rowcount == 1`.
4. Escreve o evento na cadeia com o hardstop de escopo da PR #1397 e verifica `integrity_report == MATCH` antes de `commit`.
5. Qualquer falha em qualquer verificação aciona `rollback` da transação SQLite externa, incluindo a decisão e o Outbox recém-inseridos. Não se aceita bypass nem se limpa histórico para produzir PASS.

## Critérios e limites

A CI específica executa 9 cenários novos e regressão de 12 helpers de Saga escopados, 16 de Saga/Outbox locais, 11 cross-scope Outbox, 44 de recuperação SQLite e 64 A79, em **Ubuntu e Windows**. Total previsto de **156 execuções por sistema**, 312 seleções se os dois passarem. Repetir a Quality canônica de 588 módulos/6.895 testes e Security A74 365 sem dispensa. Último baseline comprovado: 6.810 PASS, 51 FAIL e 34 ERROR.

Esta correção **somente impede que um enfileiramento local seja concluído sobre uma projeção alterada durante a mesma transação**. Não prova que a primeira operação ocorreu ou não no produtor externo, não garante que um administrador malicioso não reescreva todo o SQLite, não autentica HUMAN_OWNER, nem autoriza reenvio ou Worker. Não permite merge/deploy sem homologação explícita de todos os P0.

**Nenhuma API externa foi chamada e nenhum gasto adicional foi autorizado.**
