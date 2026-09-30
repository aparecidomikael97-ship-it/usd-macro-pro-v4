# Continuidade — Step 1 Ledger Append Contract — 30/09/2026

## Estado

Implementado / em validação sobre a Draft PR #469.

## Entrega

- request de append vinculada ao receipt review;
- source ledger GENESIS obrigatório;
- canonical receipt Step 1 obrigatório;
- target preview 1/10 obrigatório;
- token exato derivado de três digests;
- request digest recalculado;
- acknowledgements explícitos;
- decision record;
- zero persistência;
- Step 2 separado;
- ADR-0082.

## Estado máximo

EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED

## Estado real

Nenhuma decisão real de append foi registrada.

Nenhum ledger real foi alterado.

Step 2 continua não autorizado.

## Próximo gate

Writer local atômico, PLAN ONLY por padrão, preso ao append decision digest e
ao source ledger digest atual. Mesmo depois do append, Step 2 terá preflight e
decisão próprios.
