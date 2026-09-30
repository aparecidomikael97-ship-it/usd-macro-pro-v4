# AION BUSINESS — Equipe & Acessos · Step 1 Decision Record V1

## Objetivo

Registrar, no futuro, uma decisão humana formal para exatamente o primeiro
lifecycle step sem confundir decisão com execução.

## Pré-condição

O Step 1 preflight packet precisa estar no estado:

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET

e seu binding precisa ser íntegro.

## Template

Use uma cópia local de:

    deploy/sandbox/team-access/step1-decision-record.template.json

Preencha somente após revisar o packet real.

## Token exato

    AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_CREATE_INDIVIDUAL_SANDBOX_ACCOUNT

"vamos lá", "ok" ou "pode seguir" não são aceitos.

## Freshness

No momento da decisão:

- packet: máximo 300 segundos desde evaluated_at;
- observação: máximo 900 segundos desde observed_at.

## Validação

    python validate_team_access_step1_decision.py <step1-packet.json> <decision-record.json> --output <verified-step1-decision.json>

## Estado máximo

EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED

O estado concede somente autorização manual futura para Step 1. O CLI não
executa a criação da conta sandbox e não altera o ledger.
