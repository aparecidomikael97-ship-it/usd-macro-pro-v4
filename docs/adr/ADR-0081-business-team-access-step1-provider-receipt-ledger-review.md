# ADR-0081 — Business Team Access Step 1 Provider Receipt and Ledger Review

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0080 pode futuramente produzir um receipt sanitizado após o POST físico do
Step 1. Esse receipt não deve entrar diretamente no lifecycle ledger.

Antes do append é necessário validar toda a cadeia causal e reconstruir o
receipt canônico do lifecycle.

## Decisão

Adicionar uma camada read-only que exige:

- materialization válido;
- Authorization Package válido;
- Step 1 preflight packet íntegro;
- execution envelope íntegro;
- apply plan íntegro e preso ao envelope;
- runner preflight íntegro e em APPLY;
- provider receipt sanitizado.

## Provider receipt

O receipt físico precisa carregar e coincidir com:

- apply_plan_digest;
- runner_preflight_digest;
- execution_envelope_digest;
- operator_session_id;
- baseline_evidence_digest;
- Step 1;
- username sandbox;
- provider KEYCLOAK;
- realm atlasquant-sandbox;
- provider_user_id;
- HTTP 201;
- exact_readback_verified=true;
- executed_at válido.

Também precisa declarar:

- secret_material_included=false;
- access_token_included=false;
- authorization_token_included=false;
- ledger_append_authorized=false;
- automatic_ledger_append=false;
- production_targeted=false.

## Janela temporal

A execução física precisa ocorrer no máximo 180 segundos depois do evaluated_at
do runner preflight.

## Canonical lifecycle receipt

A camada calcula um provider_evidence_digest e usa esse digest para construir o
receipt canônico do Step 1 com:

- previous_entry_digest = GENESIS;
- mutation_observed=true;
- sandbox_only=true;
- production_targeted=false;
- secret_material_included=false.

## Ledger preview

O receipt canônico é aplicado somente em memória a um preview do ledger.

O resultado esperado é:

- completed_count = 1;
- next_expected_step_order = 2;
- next_expected_step_id = ENROLL_STRONG_AUTH;
- automatic_next_step_authorized=false.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_STEP1_LEDGER_APPEND_REVIEW

## Segurança

Esse estado:
- não grava o ledger;
- não autoriza append;
- não autoriza Step 2;
- não habilita executor;
- não autoriza produção/deploy/runtime.

## Compatibilidade

Complementa ADR-0069, ADR-0070, ADR-0076, ADR-0080.
