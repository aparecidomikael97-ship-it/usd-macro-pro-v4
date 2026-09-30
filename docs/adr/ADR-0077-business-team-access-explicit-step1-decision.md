# ADR-0077 — Business Team Access Explicit Step 1 Decision Record

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0076 produz um packet íntegro e fresco para a decisão manual do primeiro
lifecycle step. Esse packet não é autorização.

A decisão do Step 1 precisa ser um registro explícito, curto-lived e preso ao
packet exato.

## Decisão

Adicionar um Step 1 Decision Record com:

- token exato do packet;
- step1_packet_digest exato;
- target order = 1;
- target id = CREATE_INDIVIDUAL_SANDBOX_ACCOUNT;
- decided_by igual ao observador/administrador do packet;
- timestamp com timezone;
- packet com no máximo 300 segundos desde avaliação;
- observação com no máximo 900 segundos desde coleta;
- acknowledgements completos.

## Token

AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_CREATE_INDIVIDUAL_SANDBOX_ACCOUNT

Mensagens genéricas como:

- vamos lá;
- ok;
- pode seguir;
- autorizado;

não substituem o token formal.

## Estado máximo

EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED

Esse estado significa apenas:

manual_step1_execution_authorized = true

Ele não significa que a execução ocorreu.

## Segurança

Mesmo com decisão válida:

- step_execution_performed = false;
- ledger_append_authorized = false;
- automatic_execution_authorized = false;
- automatic_ledger_append = false;
- executor_enabled = false;
- production/deploy/runtime = false.

O próximo componente, se criado, deve revalidar packet + decision record antes
de preparar qualquer execução física.

## Compatibilidade

Complementa ADR-0070, ADR-0075 e ADR-0076.
