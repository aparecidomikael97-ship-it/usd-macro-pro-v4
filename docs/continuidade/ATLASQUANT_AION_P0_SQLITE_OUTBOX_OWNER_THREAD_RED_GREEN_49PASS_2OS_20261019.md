# AtlasQuant / AION — P0 SQLite: proteção explícita da thread proprietária do Outbox — RED→GREEN

Data: 19/10/2026. **GO-LAB limitado para Outbox**. Nenhuma homologação geral SQLite, nenhum dos 6 P0 fechado: **0/6 P0, HARD NO-GO**, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy, sem fornecedor, sem custo, sem credenciais reais ou ação externa.

## 1. Ponto de partida e falha original demonstrada

Base do P0 SQLite anterior: branch `lab/aion-p0-sqlite-nested-tx-safe-denial-20261019` no commit `df8cd72938a6d91eeb681211056b2ecdf2a3a267`. Outbox já possuía recusa explícita `OUTBOX_NESTED_TRANSACTION_UNSUPPORTED`, com 37/37 PASS por SO; o banco `aion_chat/store.py` permanece o original A118, Git blob `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`.

Falha reproduzida: reutilizar um objeto `ExecutionOutbox` na thread não proprietária causava `sqlite3.ProgrammingError` em consultas/escritas. No caminho `enqueue`, o código chamava `store.require_healthy()` antes de detectar a thread errada, provocando `StorageUnavailableError` com `DATABASE_ERROR:ProgrammingError` e podendo marcar o estado de saúde como FAILED sem corrupção do banco. Não foi demonstrada duplicação de efeito nem envio real.

## 2. Artefatos, testes pré-correção e fix

- Branch isolada `lab/aion-p0-sqlite-owner-thread-denial-20261019`.
- `test_aion_p0_sqlite_owner_thread_denial_lab.py` — 12 casos escritos ANTES da correção, commit `60693f093b7d44d105313ce93ee58be364eefd9e`.
- `.github/workflows/aion-p0-sqlite-owner-thread-denial-lab.yml` — read-only, `contents:read`, Ubuntu+Windows, commit `a2441f23ff601dcf9e2c3260eb48da9326363dd2`.
- **RED demonstrado**: [Actions #39314984575](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39314984575), Ubuntu job `118273989523`: 12 cenários, **8 ERROR e 2 FAIL**, somente 2 PASS. Casos de leitura/lista/efeitos/release/claim/despacho/reconciliação resultavam em `sqlite3.ProgrammingError`; `enqueue` cruzado acionava health fail; teste de preservação de transação externa também não recebia recusa tipada. Este RED é de comportamento de interface, não comprova efeito externo.
- Primeiro fix `466d919517cf94568db7632ac97b12aa30b09835` no arquivo **`atlasquant_aion_execution_outbox.py` em LAB**: registrar thread proprietária no construtor e negar chamadas de outra thread antes de `self.db.execute` e de `store.require_healthy()`. Guard usado por `_scope_args`, `enqueue`, `release_expired_claims`; `get`, `list`, `effect_count`, `claim_next`, `dispatch_claimed`, `reconcile` transitam pelo guard antes de IO no escopo testado.
- Atualização de expectativa apenas no **teste LAB anterior** `test_aion_p0_original_sqlite_compat_concurrency_restore_lab.py` commit `036b528a0665caeb3fc98978811affc0dfb0ae2b`: `sqlite3.ProgrammingError` passa a `RuntimeError("OUTBOX_SQLITE_CONNECTION_THREAD_MISMATCH")` para a interface Outbox, preservando o mesmo teste de isolamento e todos os demais.
- Primeiro **GREEN** [Actions #39315156604](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39315156604): Ubuntu e Windows concluídos SUCCESS com 49/49 cada.
- **Revisão de robustez** `015b4cf34b8be0251ba3bef5bb89ac69c08d8ebb`: guard compara `threading.current_thread() is self._connection_owner_thread`, em vez de comparar IDs numéricos de threads (que podem ser reutilizados). Isso mantém `sqlite3.connect(... check_same_thread=True)` intacto, sem alterar journaling, isolamento, transações nem permitir compartilhamento de handle entre threads.
- **GREEN FINAL** [Actions #39315446770](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39315446770) COMPLETED SUCCESS, head `015b4cf34b8be0251ba3bef5bb89ac69c08d8ebb`:
  - Ubuntu job `118275607716`: **12 novos + 7 nested-transaction + 8 compat/restore + 22 A110/A63-A65 = 49/49 PASS**.
  - Windows job `118275608256`: **12 + 7 + 8 + 22 = 49/49 PASS**.
  - **49 casos distintos e 98 execuções de casos PASS**.
  - Confirmado `P0_SQLITE_THREAD_A118_BASE_PINNED` na CI: A118 Outbox fonte base SHA `6bad4ee9ba5909bbb49c609a5d3ac3c05c16ab83`, store original `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`.

## 3. O que o GREEN significa

- Objeto `ExecutionOutbox` usado indevidamente em outra thread é **recusado antes de chamar APIs SQLite ou inspecionar adapter callbacks**, com erro tipado e não permissivo `OUTBOX_SQLITE_CONNECTION_THREAD_MISMATCH`.
- Preserva dados/estado local de `PENDING`, tentativas 0, efeitos 0, saúde do banco no cenário testado, transação externa sob posse da thread original e controles de idempotência/no-send.
- Uma conexão SQLite própria criada e utilizada dentro de outra thread continua funcionando, sem desativar a proteção nativa `check_same_thread`.
- Não muda o contrato de transação aninhada e a negativa de produtor independente segue ativa. Não executou o Worker nem `adapter.send`.
- A alteração é **somente de Outbox em branch LAB**, ainda não integrada em `main`.

## 4. Lacunas e próximos gates — ainda P0 ABERTOS

1. **O guard NÃO cobre automaticamente todas as APIs de `SQLiteChatStore` e outros consumidores SQLite.** Chamadas diretas ao `store.db`, outras classes ou métodos públicos podem ainda lançar `ProgrammingError` na thread errada. Levantar callers reais e corrigir contrato de thread/banco de forma abrangente, sem habilitar `check_same_thread=False` sem design auditado.
2. **Não confundir o erro de interface corrigido com os dois IDs canônicos dos P0 SQLite.** Precisa rastrear evidência original/contratos de leitura/escrita de cada P0 e executar testes completos, concorrência, crash, isolamento e auditoria independente antes de qualquer baixa.
3. **Restauração de backup antigo:** `SQLiteChatStore.restore_from_backup` ainda aceita um SQLite estruturalmente válido que apaga `UNCERTAIN` posterior; a suíte anterior e a desta rodada reproduzem essa lacuna. Exige high-water independente do backup/host e antirollback atômico autenticado. Nenhuma correção de thread resolve isto.
4. H0 físico, recibos de produtor, credenciais HUMAN_OWNER, ZERO_AUTO_RESEND, M71 e Quality/Security históricos continuam pendentes; 49 PASS não é Quality verde, produção segura ou P0 homologado.
5. Próxima etapa: auditoria de APIs do `SQLiteChatStore` usadas fora de Outbox (especialmente erros em health/recovery) e verificação de isolamento/cleanup entre threads e no Windows; preparar RED específico antes de qualquer patch.
6. Sem mudança de branch protegida, merge, deploy, gastos ou contato real com fornecedor/cliente.

**Estado operacional inalterado: HARD NO-GO, 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND.**
