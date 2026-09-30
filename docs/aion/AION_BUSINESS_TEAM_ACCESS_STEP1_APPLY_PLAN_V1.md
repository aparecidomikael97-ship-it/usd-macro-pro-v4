# AION BUSINESS — Equipe & Acessos · Step 1 Provider Apply Plan V1

## Objetivo

Congelar exatamente o que um futuro runner manual poderia pedir ao Keycloak,
sem gerar comando executável e sem tocar no provider.

## Entrada

Execution Envelope no estado:

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY

## Operação congelada

- Keycloak sandbox;
- realm atlasquant-sandbox;
- POST /admin/realms/atlasquant-sandbox/users;
- body mínimo de UserRepresentation;
- expected HTTP 201;
- conflito 409 = hard stop.

O body não inclui credential/password/token.

## CLI

    python build_team_access_step1_apply_plan.py <execution-envelope.json> --output <step1-apply-plan.json>

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_REVIEW

Esse estado não é execução e não gera comando PowerShell/cURL.

## Próximo gate

Somente depois de revisar o apply plan poderá existir um runner manual separado.
Esse runner ainda deverá exigir autorização/digest exatos e produzir receipt
sanitizado antes de qualquer append no ledger.
