# AION B2B — Owner Renewal Action Command Plan V2

Status: **red-team hardening / não executável / Draft**.

## Motivo

O Red Team apontou três pontos no V1:

1. `trusted_scope` era recebido como argumento separado;
2. identidades usavam helper com truncamento;
3. não estava explícito que `operation_kind` é derivado da `action_family`.

## Hardening V2

O V2:

- remove `trusted_scope` da API pública;
- deriva owner/tenant/workspace do registro de execução persistido;
- exige que o scope duplicado do registro e o execution preflight sejam idênticos;
- rejeita identidades acima do limite em vez de truncá-las;
- rejeita identidades que precisariam de normalização de whitespace;
- exige `execution_request_digest` SHA-256 válido;
- mantém `operation_kind` como derivação determinística de `action_family`;
- registra `scope_source=PERSISTED_EXECUTION_RECORD`;
- registra `operation_kind_source=DERIVED_FROM_ACTION_FAMILY`;
- recalcula o `command_plan_digest` sobre o conteúdo V2.

## Disposição dos achados

**F1:** mitigado no V2 removendo a entrada de scope independente.

**F2:** mitigado no V2 com rejeição de overflow/normalização em vez de truncamento.

**F3:** não é escalada de autoridade. O writer não fornece `operation_kind`; ele
assina/binda `action_family`. O V2 deriva localmente o único operation kind
permitido para essa família e registra sua proveniência.

## Limite

O V2 continua sem endpoint, credencial, segredo, request real, payload
executável, shell, provider call, billing, contato com cliente, deploy ou
mutação de produção.

Estado máximo:

`READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW`.
