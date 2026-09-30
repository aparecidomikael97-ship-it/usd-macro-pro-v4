# AION BUSINESS — Equipe & Acessos · Step 1 Receipt Review V1

## Objetivo

Validar a evidência física do Step 1 e provar, em memória, que o lifecycle
ledger ficaria coerente com exatamente 1/10 concluído.

## Entrada

O CLI recebe:

1. materialization;
2. Authorization Package;
3. Step 1 preflight packet;
4. execution envelope;
5. apply plan;
6. runner preflight;
7. provider execution receipt.

## CLI

    python validate_team_access_step1_provider_receipt.py <materialization.json> <authorization-package.json> <step1-preflight.json> <execution-envelope.json> <apply-plan.json> <runner-preflight.json> <provider-receipt.json> --output <receipt-review.json>

## Resultado

Estado máximo:

    READY_FOR_ADMIN_TEAM_ACCESS_STEP1_LEDGER_APPEND_REVIEW

O output contém:

- provider_evidence_digest;
- canonical_lifecycle_receipt;
- ledger_preview;
- receipt_review_digest.

## Ledger preview

O preview precisa resultar em:

- Step 1 concluído;
- completed_count=1;
- Step 2 = ENROLL_STRONG_AUTH;
- nenhum next step autorizado automaticamente.

## Fronteira

O CLI não escreve nem substitui um ledger persistido. O append continua sendo
uma decisão administrativa e uma operação separada.
