# ATLASQUANT/AION — Checkpoint Mestre P0 SQLite: Saga guard thread RED→GREEN, 74 PASS por SO

19/10/2026 | **HARD NO-GO, 0/6 P0 homologados**, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/custos/adapters/credenciais ou efeito externo.

## Repositório e rastreabilidade
- GitHub `aparecidomikael97-ship-it/usd-macro-pro-v4`.
- Baseline A118 imutável: `c62fab663c6349d7320f7843c8d09587c514426b`; `atlasquant_aion_execution_saga.py` original blob `f4fed4639930e10cd3ce7f6f724b920b9a642b26`.
- LAB isolado: `lab/aion-p0-sqlite-saga-owner-thread-20261019`, derivada do LAB de cleanup `1cf092cdb4deaa6faa10c35f017e61bffde91580`.
- 12 novos testes em `test_aion_p0_sqlite_saga_owner_thread_lab.py`, commit inicial `ee44bd2f5142029208e6b68bb270fed2f0566ef0`.
- CI `.github/workflows/aion-p0-sqlite-saga-owner-thread-lab.yml` commit `e2136d363a8f27d7e25d0a5e7892ca0a7e9347ca`: `contents: read`, matriz Ubuntu/Windows, cache de permissões não concedido. Pin de store LAB (`faafd3b61e90f3a4b3c863dcfc97b83ba32a0f3b`) e Outbox LAB (`cd78ed43ad63888408eb599e28379c193c541de2`); original Saga SHA conferido no ancestral.
- Documento de limites `docs/aion/AION_P0_SQLITE_SAGA_OWNER_THREAD_RED_GREEN_LIMITS_20261019.md` commit `a26570a0feba06110ac06a32e183f2569ec46f23`.

## RED real e erro de coleta distinguido
A primeira CI [#39318530675](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39318530675) não descobriu 12 testes porque o import da classe de teste histórica fazia o unittest coletar 32; isso **não foi RED do Saga**. Corrigida só a forma da importação do teste (sem alterar asserts) no commit `83d07e089c3a3394ac00591304f009c2778ea3f4`.

**RED de produto confirmado**: [#39318653243](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39318653243), Ubuntu job `118286884339`: **9 ERROR e 1 FAIL entre 12**; 2 PASS. Métodos `get`, `create`, `enqueue_next`, `integrity_report`, sync/compensation e transação externa acessavam diretamente `self.db` e recebiam `sqlite3.ProgrammingError` na thread estrangeira. `authority_guard` não exigia previamente a recusa por owner thread. Não foi demonstrado efeito externo, transação perdida nem corrupção de disco — apenas limite de API com erro não tipado e falta de negação no orçamento.

## Correção localizada
Commit `0a3bc46aff061695f59e155dec2ff81497d6f9c1`, alteração SOMENTE `atlasquant_aion_execution_saga.py` em LAB, blob `c34c27aa399f9744f6395e40d0277bc9f648cabf`.

Adiciona `_require_connection_thread()` que delega ao `SQLiteChatStore._require_connection_thread()`. Aplica o guard antes do primeiro SQL nos caminhos que usam `_scope_args()`, antes do `BEGIN IMMEDIATE` em `enqueue_next()` e antes de `authority_budget.guard()` em `authority_guard()`. A negação `StorageUnavailableError(SQLITE_STORE_CONNECTION_THREAD_MISMATCH)` é explícita, em vez de permitir que o driver SQLite lance erro genérico. NENHUM SQL, reenvio, adapter, Worker, compensação, approval, gate, esquema ou persistência foi alterado. `check_same_thread=True` foi preservado.

## Validação GREEN final (logs examinados)
[GitHub Actions #39318854679](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39318854679), `completed/success`, head `0a3bc46aff061695f59e155dec2ff81497d6f9c1`.

| Casos por SO | Ubuntu job `118287330957` | Windows job `118287330599` |
|---|---:|---:|
| P0 Saga direct SQLite + transaction owner / budget | 12 PASS | 12 PASS |
| A63/A64/A65 Saga original regression | 18 PASS | 18 PASS |
| Staged host cleanup cross-thread | 10 PASS | 10 PASS |
| SQLiteChatStore thread/health | 15 PASS | 15 PASS |
| Outbox thread/health | 12 PASS | 12 PASS |
| Nested transactions owner isolation | 7 PASS | 7 PASS |
| **TOTAL** | **74 PASS** | **74 PASS** |

**148 execuções de casos, 74 cenários distintos.** O log de cada job confirma os contadores e as âncoras A118/Store/Outbox. A CI é limitada e **NÃO substitui Quality/Security canônicos completos**.

## O que NÃO está resolvido / próximo foco
1. `CumulativeAuthorityBudget` mantém uma referência própria `self.db=store.db` e aceita chamadas **diretas**, sem passar necessariamente pelo guard de `Saga.authority_guard`. Precisará de auditoria original e RED→GREEN específico, incluindo thread errada, estado de health, transação externa e escrituração de orçamento, sem conceder autoridade.
2. `SQLiteChatStore.db` continua acessível diretamente; controles de store, Outbox e Saga não substituem auditoria ampla de todas as classes/clientes que guardam o handle.
3. A restauração de SQLite de backup íntegro ANTIGO continua apagando o `UNCERTAIN` local e permitindo novo claim local após restore. Witness/high-water com custódia realmente independente continua ausente. Hard stop do fornecedor impede send real, mas nenhum P0 foi fechado.
4. Recovery H0 após reinício físico, teste de corte de energia/FSYNC, prova de emissor real, HUMAN_OWNER/biometria real, RED M71, regressões canônicas Quality/Security e auditoria externa seguem pendentes. A correção de thread não prova nada disso.
5. Nenhum merge, deploy, gasto, credencial, envio real, Worker ou outro ambiente operacional foi alterado.

**Decisão de continuidade:** avançar para proteção do consumidor SQLite direto `CumulativeAuthorityBudget` ou rastreio dos dois IDs canônicos P0 históricos, sempre sem contar RED→GREEN de pequenas interfaces como homologação global. HARD NO-GO mantido.
