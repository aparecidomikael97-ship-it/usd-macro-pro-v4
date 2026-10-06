# AION B2B — Rollback + Compensation Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Separar de forma explícita:

1. reversão pré-execução/sintética já provada; e
2. qualquer futura compensação real de um efeito externo.

O fato de o Adapter V2 provar
`PRE_EXECUTION_STAGING_REVERSAL_ONLY`
NÃO prova que um efeito real de produção possa ser desfeito.

## Estado máximo

`READY_FOR_ROLLBACK_COMPENSATION_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_FRESH_OWNER_EXECUTION_AUTHORIZATION_CONTRACT_ONLY`

## Classes de reversibilidade

- REVERSIBLE_PRE_EXECUTION_ONLY
- COMPENSATABLE_EXTERNAL_EFFECT
- MANUAL_REMEDIATION_REQUIRED
- IRREVERSIBLE_EXTERNAL_EFFECT

## Provas futuras obrigatórias

Antes de qualquer compensação real:

- before_state_digest e after_state_digest vinculados;
- rollback_plan_digest vinculado;
- classe de reversibilidade explícita;
- irreversible boundary explícita;
- side effects da compensação declarados;
- impacto FinOps declarado;
- impacto no cliente declarado;
- preconditions/postconditions;
- evidência de compensação;
- receipt de compensação;
- autorização separada;
- binding de tenant/provider/idempotency.

## OUTCOME_UNKNOWN

Se um dispatch externo já foi registrado e o resultado ficar ambíguo:

- compensação automática é proibida;
- retry automático continua proibido;
- primeiro vem reconciliação manual/autorizada;
- só depois pode existir avaliação de compensação.

## Proibição central

A evidência de rollback sintético nunca pode ser promovida para:
`production_rollback_proven=True`
ou
`production_compensation_proven=True`.

Nesta fase ambos permanecem false.

## Esta camada não faz

- rollback real;
- compensação real;
- restore de produção;
- provider call;
- network;
- billing;
- customer contact;
- CRM write;
- provisioning;
- deploy;
- production mutation.

Autorização histórica nunca vale como autorização nova.
