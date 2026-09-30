# AION BUSINESS — Equipe & Acessos · Baseline Acceptance V1

## Objetivo

Separar a validação técnica do baseline da decisão humana de aceitá-lo como
entrada para o plano de lifecycle.

## Fluxo

readiness
→ baseline
→ operator handoff
→ baseline acceptance
→ lifecycle plan
→ lifecycle authorization
→ step gates.

## Registro

Use:

    baseline-acceptance-record.template.json

O token formal é:

    ACCEPT_TEAM_ACCESS_SANDBOX_BASELINE

O registro precisa copiar exatamente os digests e o operator_session_id do
handoff aprovado.

## Validação

    python validate_team_access_baseline_acceptance.py <handoff.json> <acceptance-record.json>

Estado máximo:

    EXPLICIT_SANDBOX_BASELINE_ACCEPTANCE_VERIFIED

Esse estado autoriza somente o baseline como input do lifecycle plan.

## Builder

O builder do lifecycle agora exige baseline_acceptance válido. Baseline técnico
sem aceitação não gera plano.

## Produção

Nenhuma aceitação de baseline autoriza produção ou execução do lifecycle.
