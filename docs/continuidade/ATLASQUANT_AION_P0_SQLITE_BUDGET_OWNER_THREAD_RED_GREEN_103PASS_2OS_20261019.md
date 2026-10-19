# Checkpoint Mestre — P0 SQLite / CumulativeAuthorityBudget: RED→GREEN 103 PASS por SO — 19/10/2026

**Veredito:** GO-LAB somente para correção de compatibilidade thread/transação no ledger de orçamento de autoridade; **NÃO homologado**. **0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND.** Sem merge em main, deploy, execução externa, gasto novo ou credenciais reais.

## Proveniência objetiva
- Repo: `aparecidomikael97-ship-it/usd-macro-pro-v4`.
- Base A118 original: `c62fab663c6349d7320f7843c8d09587c514426b`. `atlasquant_aion_cumulative_authority_budget.py` Git blob `be87fb5361c37f3e30c08558b804861c461ef9ea`.
- Branch isolada: `lab/aion-p0-sqlite-budget-owner-thread-20261019` a partir da correção Saga LAB `0a3bc46aff061695f59e155dec2ff81497d6f9c1`.
- 15 testes P0 predefinidos **antes** do patch: `test_aion_p0_sqlite_authority_budget_owner_thread_lab.py`, commit `bde24d1070ec84a4654dc6b7e88cc571a41ba66d`.
- Workflow Ubuntu/Windows com `permissions:contents:read`: `.github/workflows/aion-p0-sqlite-authority-budget-owner-lab.yml`, commit `d01367deb8e211c895b3d882301bb81148035036`.
- Pinos anteriores conferidos pelo workflow em ambos SO: `aion_chat/store.py` blob `faafd3b61e90f3a4b3c863dcfc97b83ba32a0f3b`, `atlasquant_aion_execution_outbox.py` blob `cd78ed43ad63888408eb599e28379c193c541de2`, `atlasquant_aion_execution_saga.py` blob `c34c27aa399f9744f6395e40d0277bc9f648cabf`. NÃO editados nessa rodada.

## RED original (falha comprovada, sem confundir com falha de CI)
- [GitHub Actions #39319932323](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39319932323), Ubuntu job `118291044829`: **9 ERROR + 2 FAIL entre 15 testes** (4 PASS) na implementação original.
- Erros `sqlite3.ProgrammingError` surgiram em leitura e gravação do `CumulativeAuthorityBudget` executadas na thread diferente daquela que criou o SQLite, porque o módulo mantém `self.db=store.db` diretamente, contornando a API central protegida. Um `guard({})` inválido foi respondido como política de binding em vez de recusar primeiro a thread, e `_scope_args()` não fazia esse teste. Isso NÃO comprova perda de dados nem autoridade extra.
- `record_confirmed` chamava `BEGIN IMMEDIATE` com conexão já em transação ou SAVEPOINT do caller; `sqlite3.OperationalError: cannot start a transaction within a transaction`. O `BEGIN` original ocorre ANTES de seu `try`, portanto **não alegar que havia rollback indevido demonstrado**. A lacuna era a recusa não explícita, não prova de que o caller perdeu a transação.
- Os 15 cenários têm asserções de ausência de escrita na thread errada, continuidade de health e transação do chamador, tentativa idempotente sintética e orçamento não autorizante.

## Patch limitado em LAB
Commit `a172c88f67e47d001b804b16808b8648cba3804e`, altera exclusivamente `atlasquant_aion_cumulative_authority_budget.py`, Git blob `3dfc54ace266b7d8dd48421570e4a9ce3eb02dcf`.

- Cria `_require_connection_thread()` que delega a `SQLiteChatStore._require_connection_thread()`.
- `_scope_args()` verifica propriedade antes de leituras `_snapshot` e escopo de efeitos.
- `guard()` verifica propriedade **antes de validar o binding**, evitando que uso de uma conexão em thread estrangeira se apresente como decisão normal de política.
- `record_confirmed()` verifica propriedade e `self.db.in_transaction` **antes** do `BEGIN IMMEDIATE`, negando com `RuntimeError("AUTHORITY_BUDGET_NESTED_TRANSACTION_UNSUPPORTED")` quando o caller possui a transação. Não tenta `commit`/`rollback` da transação externa.
- Não altera estrutura SQL, budget limits, lógica de `allowed`, idempotência, conexão `check_same_thread=True`, callback de envio, produtor, Worker ou política de autoridade.

## GREEN pós-correção: CI e logs conferidos

[GitHub Actions #39320080553](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39320080553): `completed / success`, head `a172c88f67e47d001b804b16808b8648cba3804e`.

| Testes por SO | Ubuntu job 118291552066 | Windows job 118291551794 |
|---|---:|---:|
| 15 novos P0 Budget thread / nested / ledger não autorizante | 15 PASS | 15 PASS |
| 14 originais CumulativeAuthorityBudget limites/idempotência | 14 PASS | 14 PASS |
| 12 P0 Saga owner-thread | 12 PASS | 12 PASS |
| 12 P0 Outbox owner-thread | 12 PASS | 12 PASS |
| 7 P0 nested-transaction | 7 PASS | 7 PASS |
| 10 P0 host cleanup + 15 P0 store | 25 PASS | 25 PASS |
| 18 originais A63/A64/A65 Saga/Outbox | 18 PASS | 18 PASS |
| **TOTAL** | **103 PASS** | **103 PASS** |

**103 cenários distintos; 206 execuções PASS.** Pinos A118 e módulos LAB anteriores confirmados no CI. Nenhuma regressão na matriz **focada** foi observada. Isso NÃO substitui Quality/Security integrais nem homologação externa.

## O que isso NÃO comprova, ainda bloqueado
1. `record_confirmed()` segue permitindo gravar uma **projeção local sintética** de gasto em SQLite; mesmo `effect_ref` e registro `RECORDED` **não autenticam efeito do fornecedor**. Nenhuma evidência sobre emissor real foi produzida, e não se pode usar tal registro para liberar adaptação, reenvio ou Worker.
2. Um `guard()` com `allowed=True` é filtro LOCAL: responde `grants_authority=False`, `execution_allowed_by_this_component=False`, `executes_action=False`. Não autentica HUMAN_OWNER, resultado externo, receipt ou permissão de executar.
3. O módulo ainda conserva `self.db` como referência direta. Outros consumidores e APIs que recebem `store.db` não foram exaustivamente auditados; a conexão pública pode ser usada diretamente fora dos guards da API.
4. Restauração de backup SQLite íntegro antigo ainda apaga `UNCERTAIN` e permite novo claim local sem high-water de custódia externa. Hard stop de produtor continua impedindo envio real, mas antirollback segue **NÃO RESOLVIDO**.
5. Não testados corte de energia físico, reinício H0 real, concorrência entre hosts, confirmação de recibos independente, autenticação do dono, M71 RED, Quality/Security históricos completos. Os seis P0 continuam abertos, e nenhuma revisão independente concedeu GO.

## Próximos passos de maior impacto
- Identificar todos os demais consumidores diretos de `SQLiteChatStore.db` (e os IDs canônicos dos dois P0 SQLite) e desenhar integração sem estado cross-thread indevido; foco em fonte verificável, não apenas inflar testes.
- Preparar contrato para **high-water/epoch do primeiro intento fora do domínio de backup do SQLite e do executor**, para impedir o rollback de `UNCERTAIN`. Exigir custódia independente e CAS/ledger durável, sem falso testemunho local.
- Manter HARD NO-GO até prova real de fornecedor, HUMAN_OWNER, H0 após reboot, falhas SQLite históricas e revisão integral.

**Status preservado:** 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND, nenhum merge/deploy/gasto.
