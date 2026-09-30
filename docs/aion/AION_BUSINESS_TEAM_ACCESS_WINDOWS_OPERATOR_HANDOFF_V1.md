# AION BUSINESS — Equipe & Acessos · Operator Baseline Handoff V1

## Objetivo

Amarrar o readiness real do Windows ao baseline real do sandbox sem aceitar
artefatos de sessões diferentes.

## Operator session

Get-TeamAccessSandboxReadiness.ps1 gera um operator_session_id aleatório e não
sensível.

Invoke-TeamAccessSandboxOperator.ps1 repassa esse ID para
Collect-TeamAccessSandboxEvidence.ps1.

O baseline inclui o mesmo ID.

## Validação

O CLI:

    python validate_team_access_operator_handoff.py <readiness.json> <baseline.json> --reviewed-by <admin>

valida:
- readiness;
- baseline;
- digests;
- timestamps;
- mesma sessão;
- ausência de autorização de produção/lifecycle.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW

Esse estado ainda não significa baseline aceito e não cria um lifecycle plan.

## Próximo gate

Uma decisão administrativa separada precisa aceitar o baseline/handoff antes de
usar o digest como entrada para o plano de lifecycle.
