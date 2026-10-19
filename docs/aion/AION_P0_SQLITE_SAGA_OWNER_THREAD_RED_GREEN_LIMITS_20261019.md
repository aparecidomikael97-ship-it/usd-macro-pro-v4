# AION P0 — Saga SQLite: thread proprietária de conexão e negação antes do primeiro I/O

**Data:** 19/10/2026. **Escopo:** LAB isolado do coordenador `ExecutionSagaCoordinator`; sem merge, deploy, worker, fornecedor ou operação externa. **0/6 P0 homologados; HARD NO-GO**.

## O que foi examinado
O Saga original (`atlasquant_aion_execution_saga.py`, blob `f4fed4639930e10cd3ce7f6f724b920b9a642b26`) recebe `SQLiteChatStore` e armazena uma referência direta `self.db=store.db`, fora dos guards de `SQLiteChatStore`. Múltiplos métodos, inclusive `get`, `create`, `integrity_report`, `enqueue_next` e reconciliações, acessam `self.db` sem checar a thread antes. `enqueue_next` começa diretamente com `BEGIN IMMEDIATE`. `authority_guard` delega ao orçamento de autoridade sem um guard no limite do Saga.

A conexão SQLite do store permanece com `check_same_thread=True`; é proibido eliminá-lo para ocultar esse problema. Também não se concluiu que a falha original provocava corrupção, rollback real ou qualquer efeito externo.

## RED realizado antes de editar Saga
Branch: `lab/aion-p0-sqlite-saga-owner-thread-20261019`, base no LAB de ciclo de vida SQLite `1cf092cdb4deaa6faa10c35f017e61bffde91580`.
- Testes novos em `test_aion_p0_sqlite_saga_owner_thread_lab.py`; primeiro commit `ee44bd2f5142029208e6b68bb270fed2f0566ef0`.
- A primeira execução [#39318530675](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39318530675) parou antes dos 12 testes por importação de `HistoricalFixture`, que fez o unittest descobrir **32** casos. Corrigida apenas a importação, sem mudar asserts, commit `83d07e089c3a3394ac00591304f009c2778ea3f4`.
- RED genuíno [#39318653243](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39318653243), Ubuntu job `118286884339`: **9 ERROR e 1 FAIL em 12 casos**. Nove endpoints do Saga lançaram `sqlite3.ProgrammingError` ao reutilizar o handle em outra thread; o guard de orçamento não produzia `StorageUnavailableError(SQLITE_STORE_CONNECTION_THREAD_MISMATCH)` antes da validação do próprio orçamento. Dois controles positivos passaram. Nenhuma falha demonstra envio externo ou rollback de transação confirmado.

## Patch mínimo
Commit `0a3bc46aff061695f59e155dec2ff81497d6f9c1`, arquivo **`atlasquant_aion_execution_saga.py` somente em LAB**. Define `_require_connection_thread()` delegando a `self.store._require_connection_thread()`. Chama esse guard:
- em `_scope_args` antes de consultas do Saga e de todos os caminhos que começam lendo `get` e eventos;
- no início de `enqueue_next` ANTES do `BEGIN IMMEDIATE`;
- no início de `authority_guard` antes de delegar ao orçamento de autoridade.

A alteração **não** muda operações SQL, persistência, esquema, compensação, assinatura, idempotência, aprovação humana, controles A63/A64/A65, critério de produtor nem configuração SQLite. Continua sem habilitar Worker/adapter; não autoriza efeitos externos.

## GREEN validado e limites
A [GitHub Actions #39318854679](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39318854679) executa os 12 contratos novos, 18 A63/A64/A65 originais, 10 host cleanup, 15 guard store, 12 guard Outbox e 7 transações aninhadas em cada SO; **74 distintos por SO**. O resultado final só deve ser considerado depois de cada job `completed/success` e logs de contagem revisados.

Lacunas críticas:
- `CumulativeAuthorityBudget` também mantém `store.db` diretamente e pode ser usado sem passar pelo limite `Saga.authority_guard`; auditar chamadas diretas e construir RED específico antes de novo patch.
- `SQLiteChatStore.db` permanece público; código externo pode usar handle sem guard central, ainda sujeito ao `ProgrammingError` nativo.
- Restore de backup íntegro antigo ainda pode apagar `UNCERTAIN`, sem high-water autêntico de custódia independente. A correção de thread não corrige retrocesso.
- Não há teste físico de reboot/power-loss, Quality/Security canônicos completos, proveniência real do produtor, biometria de HUMAN_OWNER nem integração de H0. Outros P0 continuam não homologados.

**Regra atual:** 0/6 P0 homologados, HARD NO-GO, ZERO_AUTO_RESEND, Worker OFF; sem merge, deploy ou gastos. O PASS de uma matriz local não é prova de segurança operacional.
