# AtlasQuant/AION — A122: não reciclar lease expirado com decisão SQLite corrompida

**21/10/2026 · somente LAB / PR Draft · HARD NO-GO / Worker OFF / ZERO_AUTO_RESEND / 0 de 6 P0 homologados**

## Motivação e falha real

Após a PR Draft #1400, `ExecutionOutbox.get()` e `list()` passaram a identificar decisões adulteradas em SQLite, devolvendo apenas uma visão forense `local_integrity=MISMATCH`, `decision={}`, `reconciliation_state=UNKNOWN_BLOCKED`. O método de reivindicação `claim_next()` já verifica coerência local antes do novo claim.

Entretanto, **`release_expired_claims()` executava diretamente um `UPDATE action_outbox SET state='RETRY'` em qualquer linha com estado `CLAIMED`, lease vencido e marcadores de despacho vazios, independentemente da integridade da decisão associada**, porque se baseava somente nas colunas da fila.

A transição é uma mudança real de estado **antes** do `claim_next`. Se um atacante/código local modifica o `decision.data`, `authorization_ref`, `valid_until` ou o escopo, a projeção já não pode autenticar o conteúdo original. Reciclar essa intenção como `RETRY` não deve ser tratado como operação segura ou como evidência de ausência de efeito externo.

Isto é uma vulnerabilidade de integridade **local** sob adulteração do SQLite; não prova exploit remoto, envio real nem recibo de fornecedor. Mesmo uma decisão perfeita em SQLite não oferece `NO_EFFECT_FENCED` após timeout; H0 segue bloqueado.

### RED antes do patch

A bateria `tests/test_aion_p0_h0_expired_lease_integrity_fence_lab.py` usa `SQLiteChatStore` e `ExecutionOutbox` reais, transações SQLite e DBs descartáveis; nenhuma operação externa. Inicializa uma primeira intenção `CLAIMED` sem início de despacho e força o vencimento da lease. Cobre:

- `grants_authority=True` e payload modificado no JSON;
- JSON com whitespace, chave duplicada ou malformado;
- `authorization_ref`, prazo, `action` e `payload_digest` persistidos alterados;
- `owner` da linha `action_decisions` adulterado, ocultando o vínculo de escopo;
- mistura de uma lease íntegra e outra corrompida num mesmo lote (atomicidade);
- lease íntegra expirando normalmente, não expirada, marcador de despacho, segunda chamada e transação externa pré-existente.

**Evidência RED-first:** GitHub Actions [#39625126687](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39625126687), SHA `1e65e9a041c5ab8ed76ad82e31d0bc8fca75d9cc`: em Ubuntu **11 FAIL/16 testes** ao exigir recusa e rollback que o código antigo não implementava. Testes originais de hardstop mantidos.

## Mudança no código real

Em `atlasquant_aion_execution_outbox.py`, após `BEGIN IMMEDIATE` e **ANTES** do UPDATE de `CLAIMED→RETRY`:

1. Selecionar sob a mesma transação SQLite todos os IDs de leases candidatas: escopo exato, `CLAIMED` expirada, sem `dispatch_started_at`, `sent_at`, `confirmed_at`, `effect_ref` nem ledger de efeitos. A seleção coincide com o predicado de reciclagem que já existia.
2. Para cada ID selecionado, chamar `get(id)` sem qualquer mutação. Se o JOIN de escopo estiver ilegítimo ou indisponível, `LookupError` também bloqueia.
3. **Somente se todos os registros tiverem `local_integrity=MATCH`**, executar o UPDATE já existente de reciclagem e fazer commit da própria transação.
4. Se qualquer elemento do lote estiver suspeito, lançar `PermissionError("OUTBOX_EXPIRED_CLAIM_LOCAL_INTEGRITY_MISMATCH")`; o tratamento já existente faz rollback de **toda** a transação. Nenhuma intenção, mesmo saudável, é reciclada parcialmente num lote que inclui corrupção.

Esta barreira não substitui evidência independente: usa hashes e metadados localmente alteráveis. Uma restauração conjunta do banco, manifestos e head externo não matriculado não é detectada; o código não registra `NO_EFFECT` nem autoriza reenvio.

## Regressão esperada

Workflow dedicado Ubuntu + Windows: 16 testes novos +26 da quarentena #1400 +9 Outbox parent transaction #1399 +9 CAS da Saga #1398 +12 isolamento Saga #1397 +16 integração Saga/Outbox +11 SQL scoped Outbox #1396 +44 recuperação SQLite #1385 +64 H0 A79 = **207 testes por sistema, 414 execuções**, condicionadas a todos PASS no SHA final.

Workflow original de Quality canônica: 588 módulos / 6.895 testes, atualmente **6.810 PASS / 51 FAIL / 34 ERROR**; Security A74 365 PASS, H0 A79 64 PASS. Não editar a seleção da Quality, substituir critérios, atribuir PASS sem execução, mesclar ou implantar antes de homologar todos os P0.

**Nenhum merge, deploy, envio, credencial de fornecedor, assinatura externa fingida, chamada de API ou custo adicional.**
