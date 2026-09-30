# AION BUSINESS — Equipe & Acessos · Lifecycle Plan Materialization V1

## Objetivo

Transformar baseline real + acceptance explícito em um pacote concreto das 10
etapas, pronto para revisão, sem executar nada.

## CLI

    python materialize_team_access_lifecycle_plan.py <baseline.json> <baseline-acceptance.json> --test-username sandbox.operador.demo --tenant-id tenant-a --factor-type PASSKEY --requested-by admin.demo --output lifecycle-plan.json

## Validações

A materialização:
- revalida o baseline bruto;
- exige operator_session_id válido;
- exige acceptance preso ao mesmo baseline;
- exige username sandbox.*;
- exige tenant;
- limita MFA a PASSKEY / SECURITY_KEY / TOTP.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW

O plano ainda precisa da autorização explícita definida na ADR-0068 antes de
qualquer step manual.
