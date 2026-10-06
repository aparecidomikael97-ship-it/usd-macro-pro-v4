# AION B2B — Owner Renewal Action Command Plan V2

Status: **red-team hardening / não executável / Draft**.

## Motivo

O Red Team apontou três pontos no V1:

1. `trusted_scope` era recebido como argumento separado;
2. identidades usavam helper com truncamento;
3. não estava explícito que `operation_kind` é derivado da `action_family`.

## Hardening V2

O V2 remove `trusted_scope` da API pública, deriva owner/tenant/workspace do
registro de execução persistido, rejeita identidades que exigiriam truncamento
ou normalização, exige `execution_request_digest` válido e registra a
proveniência de scope e operation kind.

O V2 continua sem endpoint, credencial, segredo, request real, payload
executável, shell, provider call, billing, contato com cliente, deploy ou
mutação de produção.

Estado máximo:
`READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW`.
