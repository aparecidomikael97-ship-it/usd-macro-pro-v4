# AION BUSINESS — Lifecycle Plan Package V1

Após baseline e acceptance reais, use o CLI local:

    python build_team_access_lifecycle_plan.py <baseline.json> <acceptance.json> --test-username sandbox.operador.demo --tenant tenant-a --factor PASSKEY --requested-by <admin> --output <plan.json>

O builder exige acceptance válido. Em seguida, o package validator recalcula o
plan digest, valida a sequência 1→10 e garante que nenhuma autorização de
execução esteja presente.

Estado máximo:

READY_FOR_ADMIN_TEAM_ACCESS_LIFECYCLE_AUTHORIZATION_RECORD

O próximo gate continua sendo o registro explícito de autorização do lifecycle.
