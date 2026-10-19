# AtlasQuant / AION — P0 SQLite: concorrência, limites de compatibilidade e restauração REAL — 19/10/2026

**VEREDITO:** GO-LAB apenas para reprodução de comportamentos do SQLite/Outbox originais em Ubuntu+Windows. **NENHUM P0 HOMOLOGADO, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND.** Não houve correção de produto nesta rodada, nem deploy/merge/custo.

## Fonte e artefatos auditados
- Baseline imutável: A118 `c62fab663c6349d7320f7843c8d09587c514426b`.
- Branch isolada: `lab/aion-p0-sqlite-compat-concurrent-restore-20261019`.
- Testes novos: `test_aion_p0_original_sqlite_compat_concurrency_restore_lab.py`, commit `6df1cc7e096f0374468bfdbe9e23edc3b8dea257`.
- Workflow isolado: `.github/workflows/aion-p0-sqlite-concurrency-restore-lab.yml`, commit/head `5c7544bff377884ba015da9cd8db1b3fc25e6a0a`.
- CI [#39313142598](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39313142598) **COMPLETED SUCCESS**:
  - Ubuntu `118267668280`: 8/8 novos + 4/4 A110 + 18/18 A63/A64/A65 = **30/30 PASS**.
  - Windows `118267668669`: 8/8 novos + 4/4 A110 + 18/18 A63/A64/A65 = **30/30 PASS**.
  - **30 casos distintos, 60 execuções PASS**. O workflow confirma `P0_SQLITE_3_ORIGINAL_BLOBS_MATCH`: `aion_chat/store.py` blob `6df8ad55673acaca6eeeb0bc3e3898d7a10b08ba`; `atlasquant_aion_execution_outbox.py` `6bad4ee9ba5909bbb49c609a5d3ac3c05c16ab83`; `test_atlasquant_aion_a110_outbox_ambiguous_block.py` `2ca086e315ee629026968924bae8e64cafd3a1f1`. Código original intocado.

## Oito cenários e interpretação
1. **Concorrência multi-handle**: dois threads com suas PRÓPRIAS conexões SQLite simultaneamente competem por um claim. `BEGIN IMMEDIATE` + CAS concedem um único `CLAIMED` no teste, `attempts=1`; não provam safe use de mesma conexão em múltiplas threads ou serialização distribuída entre hosts.
2. **Lease pré-efeito vencido**: reciclado uma única vez; não representa retry após envio.
3. **Uso da MESMA conexão em thread estrangeira**: `sqlite3.ProgrammingError` esperado; nenhum registro alterado. **Limitação de compatibilidade observada, NÃO corrigida**. Não usar `check_same_thread=False` como atalho sem uma arquitetura de fila/locking e isolamento.
4. **Claim dentro de `BEGIN IMMEDIATE` já ativo**: `sqlite3.OperationalError` contendo `within a transaction`, transação externa revertida pelo teste, nenhum claim. **Limitação de composição de transações observada, NÃO corrigida**. Precisa de contrato explícito de transação proprietária versus SAVEPOINT com prova de commit/rollback.
5. **`backup_to` original** gera arquivo SQLite íntegro: isso prova integridade física/estrutural da cópia, NÃO frescor de decisões/ações.
6. **P0 DE SEGURANÇA ANTIROLLBACK REPRODUZIDO COM API ORIGINAL DE RESTORE**: `SQLiteChatStore.backup_to` antes da tentativa -> original `claim_next` -> injeção fixture de `UNCERTAIN` com `COMMIT` -> reabertura confirma `UNCERTAIN` -> `SQLiteChatStore.restore_from_backup` da cópia antiga retorna `RESTORE_VERIFIED` -> original Outbox retorna `PENDING` e permite novo `CLAIMED` local. Isso demonstra **que uma cópia estruturalmente íntegra não constitui high-water de execução independente e pode apagar uma incerteza anterior**. Sem efeito real: SQL sintético e o guard `INDEPENDENT_PRODUCER_NOT_ENROLLED` continuam impedindo qualquer `adapter.send` produtivo.
7. **Escopo distinto** não reivindica nem lê decisão de outro proprietário; teste limitado a dois scopes falsos.
8. **Marcador de possível efeito em CLAIMED** bloqueia reciclagem mesmo com lease vencido; é defesa local necessária, insuficiente para rollback do banco inteiro.

Os 18 testes históricos A63/A64/A65 já receberam correções de **cleanup de conexões de teste no Windows** na etapa A115, segundo PR Draft #1322. Esses WinError 32 históricos de teardown NÃO são evidência de que os dois P0 de leitura/escrita e concorrência ficaram homologados.

## Classificação de verdade e limites
- `30 PASS/OS` confirma oito expectativas, inclusive duas *incompatibilidades esperadas* e uma *lacuna de restore esperada*. NÃO significa 30 proteções concluídas.
- O teste 06 usa método ORIGINAL de restore, diferentemente do teste da rodada anterior que substituía manualmente o arquivo. Ele reforça o achado, mas continua sem chamada de fornecedor, energia física interrompida, nem witness independentemente matriculado.
- Não comparar cross-thread ProgrammingError e nested transaction OperationalError como necessariamente os "dois P0 históricos" sem correspondência aos IDs/logs canônicos. Precisamos de rastreio de falhas originais/contratos de caller antes da homologação.
- **A118 permanece bloqueado antes de `adapter.send`**, portanto não foi provado reenvio externo indevido.
- Quality/Security integrais, multi-processo real, Windows físico, testes sob encerramento elétrico, audit de H0/F1/T1 e testes dos P0 SQLite históricos não foram homologados por esta suíte focada.
- M71 stale READY gate permanece RED no original, M73 apenas protótipo de diagnóstico. Outros P0 independentes estão abertos.

## Próxima execução P0, ordenada
1. Congelar contractos de CALLER SQLite: thread proprietária por conexão ou worker dedicado; diferenciar leitura concorrente com conexão independente de reutilização indevida de thread; tratamentos explícitos e fail-closed em APIs públicas.
2. Separar transação EXTERNA `BEGIN IMMEDIATE` da transação do Outbox: decidir se `claim_next` deve bloquear com erro tipado (sem efeitos) ou aceitar composição SAVEPOINT com prova de commit externo. Não alterar produção até provas de concorrência/compatibilidade e revisão independente.
3. Ensaio de witness durável FORA do domínio do backup e da conta/host controladores do banco. `restore_from_backup` deve recusar retrocesso sem atestado de high-water externo. JSON e cópia da mesma VM NÃO satisfazem isso.
4. Rodar casos RED→GREEN reais no LAB, Windows/Linux, sem mascarar Quality/Security antigos; versionar checklist específico dos dois P0 e reportar o que ainda precisa de teste físico.
5. Exigir autorização para qualquer gasto, credencial real ou novo serviço e **nunca** remover hard stop de produtor/Worker enquanto 0/6 P0.

**Conclusão operacional:** fase atual 0/6 P0 homologados; Worker desligado; ZERO_AUTO_RESEND; HARD NO-GO; nenhuma alteração em `main`, nenhum merge ou deploy, nenhum efeito externo.
