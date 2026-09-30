# AION BUSINESS — Equipe & Acessos · Step 1 Preflight Package V1

## Objetivo

Chegar até a fronteira exata da decisão manual do primeiro lifecycle step, sem
executar a etapa.

## Pré-requisitos

- lifecycle materialization válido;
- Authorization Package válido;
- baseline sem drift;
- mesma operator session;
- sandbox saudável;
- OIDC válido;
- registry schema válido;
- secrets locais;
- produção ausente;
- cleanup pronto;
- observação com no máximo 15 minutos.

## Observação read-only no Windows

    .\Get-TeamAccessStep1ReadinessObservation.ps1 -ObservedBy <admin>

O resultado padrão fica em:

    %LOCALAPPDATA%\AtlasQuant\team-access-sandbox\operator\step1-readiness-observation.json

O script usa somente verificações read-only.

## Montar o pacote

    python build_team_access_step1_preflight_package.py <materialization.json> <authorization-package.json> <observation.json> --output <step1-preflight-package.json>

## Empty ledger

O pacote exige:

- zero receipts;
- completed_count = 0;
- chain_head_digest = GENESIS;
- next_expected_step_order = 1;
- next_expected_step_id = CREATE_INDIVIDUAL_SANDBOX_ACCOUNT.

## Estado máximo

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET

O token necessário para uma futura decisão explícita pode aparecer no pacote,
mas a decisão não é registrada e o Step 1 não é executado.
