# A272 — Entrada do Outbox: sem stringificação de objetos hostis (LAB 30/10/2026)

**Base:** A271 #1722. PR draft em ramificação separada. Sem merge, Worker, deploy, ordens, serviços externos, custo ou mudança operacional.

## Causa
Apesar de A267 impedir `authorize`, `cumulative_authority_guard` e `adapter.send` no despacho normal, `dispatch_claimed` fazia `_clean(idempotency_key)` e `_token(worker_id)` antes da negativa. Esses auxiliares chamam `str(value)`. `_utc(now)` também chama `str(value)` em tipos inesperados. Um objeto Python fornecido pelo host pode implementar `__str__` com efeitos colaterais, antes da recusa de SEND. `reconcile` também recebia identificador arbitrário.

## Escopo da correção
- Em `dispatch_claimed`: exige `type(idempotency_key) is str`, `type(worker_id) is str`, e `now` nulo ou `type(now) in (str, datetime)`, antes de qualquer `_clean`, `_token` e `_utc`.
- Em `reconcile`: exige ID `str` exato antes de `_clean`.
- Três testes adicionais A267 #14–16 com `__str__` hostil em identificador, worker, relógio e subclass de string; verificam zero invocações, zero efeitos, estado original e `UNCERTAIN` preservado.

## Limites
Não se trata de sandbox contra host com execução arbitrária de Python, objeto `tzinfo` controlado ou manipulação do próprio runtime; a fixture sintética em `labs/` ainda é importável. Não comprova autorização externa, custódia ou recibo independente. A rotina geral `enqueue/claim_next/get` não foi alterada. CI A267 (Ubuntu/Windows e regressões Outbox/Saga/Chaos) deve validar o HEAD final. **0/6 P0 homologadas; HARD NO-GO, UNCERTAIN=ZERO_AUTO_RESEND.**
