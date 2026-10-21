# AION P0/H0 — A125: reivindicação e liberação de lease atômicas após CAS SQLite (LAB)

**Data:** 21/10/2026. **PR Draft empilhada sobre a #1403; nenhuma integração na main.**
**Segurança operacional:** HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, 0/6 P0 homologados.

## Contexto: contrato completo dos caminhos locais

As PRs Draft #1385→#1403 trouxeram envelopes sintéticos de evidência, recuperação read-only, correção de isolamento entre tenants, consistência da Saga, bloqueios de parent-transaction, quarentena de decisões malformadas, validação do `enqueue` ANTES de COMMIT e proibição de reentrada `IDEMPOTENT` como nova primeira intenção.

Na inspeção do código consolidado, detectamos que **a primeira reivindicação e a liberação da lease ainda não tinham a mesma verificação pós-escrita**:

1. `ExecutionOutbox.claim_next` filtra decisões e escopo sob `BEGIN IMMEDIATE` e executa `UPDATE ... SET state='CLAIMED', attempts=attempts+1` com CAS; em seguida fazia `COMMIT` **ANTES de reler o claim**. Gatilhos SQLite `AFTER UPDATE` podiam modificar o material assinado localmente (sem chave externa), a lease, o estado, tentativas ou inserir uma linha em `action_effects` **dentro do mesmo commit**. Retornar `self.get(key)` após COMMIT detectaria parte da adulteração como quarentena, porém já com claim persistido.
2. `ExecutionOutbox.release_expired_claims` agora verifica cada decisão candidata **antes** de `UPDATE CLAIMED→RETRY` (PR #1401), mas confirmava a transição sem verificar as alterações de gatilhos `AFTER UPDATE`, mesmo se `attempts`, `lease_owner`, `state`, campos de decisão ou ledger fossem adulterados.
3. Ambos operam **antes** de qualquer envio real; a falha é integridade transacional LOCAL e não comprova vulnerabilidade remota ou envio via Worker.

## RED-first antes da correção (verificado)

Nova suíte `tests/test_aion_p0_h0_post_cas_claim_release_atomic_lab.py` cria `SQLiteChatStore` + `ExecutionOutbox` reais, em SQLite descartável. **31 cenários**, cobrindo:

- Primeira reivindicação legítima e segunda reivindicação local após expiração legítima;
- alteração do JSON de `grants_authority`, JSON inválido, refs de aprovação/prazo, proprietário e vínculo entre tabelas;
- falsificação do estado `UNCERTAIN`/`CONFIRMED`, `attempts`, `lease_owner`/`lease_until`, timestamps de despacho/envio e ledger de efeito;
- corrupção do lease durante a passagem para `RETRY`, inclusive lote com uma intenção saudável misturada à corrompida;
- filtro contra reciclagem de claim após marcador de início de despacho, prazo não expirado e transação externa pré-existente.

**Prova RED:** [GitHub Actions #39635989343](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39635989343), SHA `3fa0f0d6281d09e7c743af9e6c6bb349bd79bcd4`: runner Ubuntu **24 FAIL + 1 ERROR em 31 testes**, expondo commit sem validação pós-CAS, inclusive erro de JOIN quando owner foi corrompido após commit. A mesma bateria não executou serviços de fornecedor nem recebeu credenciais reais.

## Correção no código de produto em LAB

**No `atlasquant_aion_execution_outbox.py`**, mantendo os bloqueios originais:

**`claim_next`:** captura o contador `pre_claim_attempts` do candidato. **Após** `UPDATE` condicionado e `rowcount==1`, mas **antes** do COMMIT, executa `get(key)` ainda sob `BEGIN IMMEDIATE` e exige `local_integrity=MATCH`, `state=CLAIMED`, `attempts=pre+1`, lease do mesmo worker com timestamp esperado, campos de despacho/envio/confirmação/efeito/erro vazios, chave idêntica e ausência de `action_effects`. Divergência/ausência de JOIN -> `PermissionError("OUTBOX_CLAIM_POST_CAS_INTEGRITY_MISMATCH")`, rollback do commit completo.

**`release_expired_claims`:** armazena `idempotency_key` e `attempts` da seleção pré-CAS. Após UPDATE, exige que o número atualizado corresponda ao lote selecionado, e **cada** registro relido tenha `local_integrity=MATCH`, estado `RETRY`, tentativas originais, lease/efeito/markers vazios, `last_error=CLAIM_LEASE_EXPIRED_BEFORE_DISPATCH`, e nenhum `action_effects`. Um único registro suspeito -> `PermissionError("OUTBOX_RELEASE_POST_CAS_INTEGRITY_MISMATCH")` e rollback de TODO o lote.

A solução é deliberadamente fail-closed: nenhum `COMMIT` pode permanecer quando a verificação pós-CAS falha. **Não** cria ou verifica identidade independente de issuer/nonce/head, `NO_EFFECT_FENCED`, resultado remoto ou proteção contra rollback completo do SQLite.

## Testes de segurança e Quality sem waivers

Workflow LAB `.github/workflows/aion-p0-h0-post-cas-claim-release-integrity-lab.yml`: **31 novos + 236 regressões por SO = 267 métodos/OS, 534 execuções Windows+Ubuntu** se todos passarem. Suites herdadas incluem primeira intenção Saga/Outbox, enfileiramento atômico, lease integrity, quarentena, parent transaction, CAS Saga, isolamento, read-only recovery e A79.

Workflow canônico reexecuta **588 módulos/6.895 testes** e Security A74 365 em HEAD final, sem alterações na seleção de testes, sem `skip`, `xfail`, dispensas ou bootstrap de autoridade externa falsa. Baseline verificado da PR #1403: **6.810 PASS, 51 FAIL e 34 ERROR** — 85 bloqueios históricos abertos.

**Limites permanentes:** mesmo com essas transações locais coerentes, o H0 real ainda precisa da fonte independente de identidade, assinatura, recibo causal do produtor, monotonicidade/head/latest, idempotência externa e testes controlados de rollback e efeitos. 0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND. Sem merge, deploy, contratos, chamadas externas ou gastos.
