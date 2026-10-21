# AtlasQuant/AION — proteção de escopo nos auxiliares internos da Saga (LAB)

**Data:** 21 de outubro de 2026. **HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · 0/6 P0 homologados.**

## Por que isso foi auditado

A PR Draft #1396 corrigiu uma junção do `ExecutionOutbox` que permitia expor o payload de outra conta quando uma referência no SQLite era alterada. Esta rodada verifica se a mesma defesa de escopo foi mantida nas operações internas da Saga, que utiliza um SQLite compartilhado por diferentes `Scope(owner_id,tenant_id,workspace_id)`.

O método público `ExecutionSagaCoordinator.get()` já valida que o `saga_id` pertence ao escopo atual. Entretanto, dois auxiliares Python internos não repetiam essa verificação:

- `_step_rows(saga_id)` consultava a tabela `aion_execution_saga_steps` apenas por `saga_id`, de modo que uma chamada direta feita por código interno com o ID de outra Saga retornava `payload` da outra conta.
- `_append_event(saga_id,...)` consultava e inseria eventos apenas por `saga_id`, permitindo que uma chamada interna direta inserisse um evento falso na cadeia local de uma Saga de outro escopo. Um ID que não existia era rejeitado por SQLite FK, não por uma política de escopo explícita.

**Escopo da ameaça:** acesso de código Python interno à instância `ExecutionSagaCoordinator` e conhecimento ou confusão sobre o `saga_id`, não um endpoint remoto. Não há evidência de exploração em produção, nem provas de isolamento perante um administrador com acesso irrestrito ao SQLite. O `saga_id` já é chave primária global; esta correção reforça as barreiras de funções internas e não significa que o método público permitia leitura estrangeira.

## Evidência RED-first e correção

Bateria `tests/test_aion_p0_saga_scoped_internal_helpers_lab.py` cria dois coordinators reais `ExecutionSagaCoordinator` com `CumulativeAuthorityBudget`, `ExecutionOutbox`, `SQLiteChatStore` e escopos separados por proprietário, tenant ou workspace no mesmo banco descartável.

Na versão anterior ao patch, SHA `c3c121e48cea168827c40fc29a33fe16650741dd`, run GitHub Actions #39614168981 (Ubuntu), **12 testes: 6 FAIL e 1 ERROR**:
- 3 leituras internas de etapas pertencentes ao outro escopo retornaram linhas estrangeiras;
- 3 inserções de evento cross-scope foram aceitas sem `LookupError`;
- 1 inserção para `saga_id` inexistente produziu `sqlite3.IntegrityError`, ao invés de negação explícita.

A correção modifica somente `atlasquant_aion_execution_saga.py`:
1. `_step_rows` passa a filtrar a tabela de steps por uma consulta `EXISTS` sobre a Saga pai e as três identidades `owner/tenant/workspace`.
2. `_append_event` exige que `_saga_row` retorne um pai visível sob o escopo correto **antes de ler sua cadeia de eventos**.
3. O `INSERT` de evento usa `INSERT ... SELECT ... WHERE EXISTS` verificando **de novo no próprio statement de escrita** a identidade da Saga pai; se não inserir exatamente uma linha, a operação falha fechada com `LookupError`.

Os casos normais do mesmo escopo continuam funcionando e o `integrity_report` continua indicando `proof_scope=LOCAL_SQLITE_CHAIN_ONLY`, sem conceder autoridade de produtor ou antirollback. Não alteramos as APIs de efeito, Outbox/Worker, recibos externos ou o estado do P0.

## Validação e limites

- Verificar RED/green dos 12 testes novos em Ubuntu e Windows, além de regressão independente: testes existentes de Saga/Outbox internos, Outbox cross-tenant, recuperação SQLite e H0 A79.
- Repetir sem waivers a Quality original de 588 módulos e Security A74 365. Histórico anterior do HEAD #1396: **6.895 testes, 6.810 PASS, 51 FAIL, 34 ERROR**, com 85 identificadores históricos abertos.
- **Controle integral do banco ou dos administradores**, uso de uma chave de Saga de outro escopo em APIs futuras sem gate público, leitura atualizada do produtor externo, nonce independente, recibo verdadeiro e rollback em múltiplos domínios continuam problemas separados.
- Nunca transformar uma boa execução em LAB em autenticação de HUMAN_OWNER, `NO_EFFECT_FENCED`, reenvio, compensação, merge ou deploy.

**Nenhuma contratação, conta de provedor ou gasto novo.**
