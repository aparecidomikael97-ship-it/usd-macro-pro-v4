# AION V2.7 — Durable Store + Crash + Isolation Red-Team

Base canônica: `87aae292bf47c28c8fe8da43e863c694b9c9c57f`.

Branch:
`agent/drael-aion-v27-durable-store-crash-isolation-redteam-20261004`.

## Veredito por componente

- **Unified Journal Store:** PASS para os ataques executados. Nenhum patch funcional necessário.
- **Quarantine:** PASS para preservação de evidência, fail-closed e isolamento progressivo de múltiplos corrupts.
- **Recovery:** PASS para os caminhos offline executados; caminhos que exigem GitHub real continuam fora da prova offline.
- **Memory runtime:** PASS para helpers puros executados; save/load de runtime remoto não foram exercitados porque dependem do store GitHub externo.
- **Multiprocess:** não provado; concorrência exercitada com threads.
- **TOCTOU de symlink:** não provado deterministicamente.
- **Provenance × compaction:** audit/design gap já conhecido; não classificado como bug funcional.

## Escopo de segurança

O red-team não habilita execução. Em todos os caminhos observados, recovery/store continuam declarando que restauração é state-only e não dispara provider, billing ou ordens reais.

## Fault stages

Os quatro fault stages do durable journal foram exercitados:

- `BEFORE_DURABLE_COMMIT`
- `AFTER_TEMP_FSYNC`
- `AFTER_EVENT_COMMIT`
- `AFTER_HEAD_COMMIT`

O comportamento observado é fail-closed. Retry da operação já fisicamente comprometida é idempotente quando aplicável. Nenhum evento foi duplicado por lost-response.

## Corruption

Foram exercitados:

- JSON truncado;
- JSON vazio;
- record digest adulterado;
- evento ausente;
- conteúdo malformado em quarantine;
- múltiplos corrupts processados em recoveries sucessivos.

Corrupção não é promovida silenciosamente para estado seguro.

## Path safety

Foram atacados identificadores com:

- traversal Unix e Windows;
- path absoluto;
- drive Windows;
- UNC;
- NUL;
- vazio;
- `.` e `..`;
- nomes reservados Windows;
- trailing dot/space;
- nomes excessivamente longos;
- symlink na root.

As APIs públicas permanecem fail-closed.

## Scope isolation

Tenant, owner e workspace divergentes não recuperam dados do escopo original. A mesma idempotency key pode existir de forma independente entre tenants sem colisão global.

## Concurrency

Dois writers thread-based para a mesma operação produziram exatamente um `PERSISTED` e um `IDEMPOTENT`.

Isso **não prova multiprocess**. O store possui lock baseado em `flock/msvcrt`, mas a garantia multiprocess não foi exercitada nesta auditoria.

## Recovery

Casos offline exercitados:

- candidato íntegro;
- digest mismatch;
- mesmo conteúdo do runtime atual;
- runtime SHA ausente;
- candidate integrity MISMATCH;
- approval exact-bool.

`approved` exige `is True`; valores truthy não equivalem a aprovação.

O preflight é read-only e retorna `executes_action=False`.

Caminhos que dependem de `load_checkpoint_revision` / `save_runtime_checkpoint` com GitHub real não foram exercitados como side effect externo.

## Memory

Helpers puros exercitados:

- `checkpoint_integrity_report`;
- `checkpoint_source_digest`;
- `default_checkpoint`;
- `ensure_operating_checkpoint`.

Provado:

- checkpoint default => CONFIRMED;
- tamper de componente protegido => MISMATCH;
- ausência => UNKNOWN;
- estrutura antiga/incompleta => MIGRATION_REQUIRED ou equivalente fail-closed;
- source digest muda com conteúdo;
- cópia efetivamente idêntica mantém digest;
- normalização interna não colapsa whitespace interno;
- `ensure_operating_checkpoint` preserva estados de área e não habilita real trading.

Persistência remota de memory não foi exercitada porque `save_runtime_checkpoint` / `load_runtime_checkpoint` são superfícies GitHub externas.

## Side-effect guards

Store recover/quarantine, helpers puros de memory e recovery preflight foram executados com socket e subprocess proibidos. Nenhuma chamada externa foi realizada nesses caminhos.

## Limitações

- multiprocess: NOT PROVEN;
- TOCTOU determinístico: NOT PROVEN;
- save/load GitHub remoto: não exercitado offline;
- restore aprovado com write real: não exercitado;
- autenticação externa de origem: fora do escopo deste red-team;
- provenance granular após compaction: design gap, não bug comprovado.

## Arquivo executável

`test_atlasquant_aion_v27_durable_store_crash_isolation_redteam.py`

A suíte persiste os cenários de store, quarantine, recovery offline, memory puro e side-effect guard.

## Política de patch

Nenhum bug funcional de produção foi comprovado nesta rodada. Portanto não há patch funcional. A entrega é cobertura red-team persistida + documentação.

ZERO MERGE. ZERO DEPLOY. ZERO PROVIDER. ZERO BILLING. ZERO PAID API. ZERO REAL ORDER. ZERO EXTERNAL EXECUTION.
