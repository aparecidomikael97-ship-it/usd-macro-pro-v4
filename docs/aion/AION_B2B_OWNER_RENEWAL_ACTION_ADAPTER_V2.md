# AION B2B — Adapter V2 reconciliado com Command Plan V2

Status: **Draft / sintético / offline / zero execução real**.

Esta camada preserva integralmente a entrega verde da Draft PR #874 e adiciona
uma ponte hardenizada para o Command Plan V2 do Red Team.

## Mudança principal

A API pública V2 não recebe `trusted_scope`.

O scope vem do registro de execução persistido e é reconstruído pelo Command
Plan V2. O adapter, dry-run e receipt V2 só aceitam essa cadeia reconstruída.

O binding V2 inclui também:

- `execution_request_digest`;
- `command_plan_digest` V2;
- provenance `PERSISTED_EXECUTION_RECORD`;
- provenance `DERIVED_FROM_ACTION_FAMILY`.

## O que continua igual ao V1 do Codex

- ambiente exclusivamente sintético;
- adapter class offline;
- FinOps máximo de R$200/mês;
- rollback apenas de staging pré-execução;
- dry-run sem provider;
- receipts exclusivamente sintéticos;
- zero endpoint/token/credential/payload;
- zero cobrança;
- zero contato;
- zero CRM;
- zero provisionamento;
- zero deploy;
- zero mutação de produção;
- zero comando executável.

## Compatibilidade

O V1 permanece preservado e testável como evidência da entrega original.

A cadeia V2 rejeita um command plan V1. O futuro contrato de executor deve
consumir somente o Adapter V2 reconciliado, nunca o V1 diretamente.

Estado máximo:

`READY_FOR_CONTROLLED_ACTION_ADAPTER_DRY_RUN`

seguido por:

`DRY_RUN_READY`

e, para receipt sintético:

`SYNTHETIC_RECEIPT_VALIDATED`.

Nenhum desses estados é autorização de execução.
