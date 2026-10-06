# AION B2B — Future Executor Capability / Readiness Contract V1

Status: **design-only / provider-neutral / non-executable / fail-closed**.

## Objetivo

Definir o que um futuro executor teria que provar antes que qualquer implementação
real pudesse ser sequer revisada.

Esta camada NÃO cria executor e NÃO escolhe provider. Também NÃO contém endpoint,
credencial, segredo, token, método HTTP, headers, payload, shell command,
executable command ou alvo de produção.

## Entrada obrigatória

A única entrada é uma boundary V2 previamente aprovada com estado:

`READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW`

e próximo passo:

`DESIGN_EXECUTOR_CONTRACT_ONLY`

Qualquer autoridade/effect flag ligada bloqueia o contrato.

## Estado máximo

`READY_FOR_FUTURE_EXECUTOR_CAPABILITY_DESIGN_REVIEW`

Isso continua sendo apenas arquitetura.

O próximo passo permitido é somente:

`DESIGN_REAL_RECEIPT_AUTHENTICATOR_CONTRACT_ONLY`

## Famílias abstratas suportadas

- RENEWAL → CONTRACT_CONTINUITY
- RENEWAL_WITH_CHANGES → CONTRACT_CHANGE
- NON_RENEWAL → SERVICE_OFFBOARDING
- REMEDIATION → SERVICE_REMEDIATION
- CAPACITY_RESCOPE → CAPACITY_CHANGE
- REPRICING → COMMERCIAL_PRICING_CHANGE
- INCIDENT_REMEDIATION → INCIDENT_REMEDIATION
- SERVICE_PAUSE → SERVICE_PAUSE
- SERVICE_TERMINATION → SERVICE_TERMINATION

Esses nomes descrevem intenção de negócio. Não materializam provider, request,
endpoint, payload ou comando.

## Provas futuras obrigatórias

Antes de qualquer executor real existir, ainda deverão existir contratos separados
e red-team para:

1. authenticated real receipt;
2. idempotência persistente + replay protection;
3. rollback/compensação de produção;
4. autorização fresca do Owner;
5. guard de FinOps em runtime;
6. binding de tenant/scope;
7. attestation do adapter/provider;
8. receipt de observabilidade/auditoria.

## Regras permanentes

- autorização histórica nunca é reutilizada;
- design não equivale a autorização;
- provider-neutral até existir contrato específico e aprovação;
- qualquer execução real exige nova autorização explícita do Owner;
- billing, contato com cliente, CRM write, provisionamento, deploy e produção
  continuam proibidos nesta fase.
