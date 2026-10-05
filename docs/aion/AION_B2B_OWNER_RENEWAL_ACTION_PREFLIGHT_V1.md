# AION B2B — Owner Renewal Action Preflight V1

Status: **staging / eligibility only / no business action**.

## Objetivo

Criar o gate fail-closed entre uma decisão recorrente já assinada, persistida e
atestada e uma futura cerimônia de autorização da ação comercial.

O preflight **não autoriza e não executa** a ação.

## Cadeia de provas exigida

O resultado só pode ficar elegível quando houver, ao mesmo tempo:

1. persistência exata da decisão atestada;
2. writer do checkpoint criptograficamente atestado;
3. Owner Renewal Review Packet original e imutável;
4. ciclo recorrente value-bound original e imutável;
5. ambiente de ação recente e seguro.

São vinculados:

- owner / tenant / workspace;
- customer / pilot / package;
- review type;
- escolha exata;
- digest do Owner Review Packet;
- digest do service cycle;
- digest do contrato;
- digest da conversão value-bound;
- decision-record digest;
- persistence receipt digest;
- after-checkpoint digest;
- writer request digest.

## Famílias de ação

As escolhas persistidas são classificadas sem serem executadas:

- RENEW_AS_IS_REVIEW → RENEWAL;
- RENEW_WITH_CHANGES_REVIEW → RENEWAL_WITH_CHANGES;
- NON_RENEWAL_REVIEW → NON_RENEWAL;
- REMEDIATION_PLAN_REVIEW → REMEDIATION;
- RESCOPE_CAPACITY_REVIEW → CAPACITY_RESCOPE;
- REPRICE_REVIEW → REPRICING;
- INCIDENT_REMEDIATION_REVIEW → INCIDENT_REMEDIATION;
- PAUSE_SERVICE_REVIEW → SERVICE_PAUSE;
- TERMINATION_REVIEW → SERVICE_TERMINATION.

## Ambiente de ação

A evidência precisa estar VERIFIED, ter no máximo 300 segundos e comprovar:

- isolamento do tenant;
- receipts de auditoria;
- snapshot do serviço recente;
- snapshot do contrato recente;
- estado de suporte conhecido;
- estado de cobrança conhecido;
- estado de capacidade conhecido;
- projeção customer-safe pronta;
- plano de rollback/reversão;
- nenhum incidente de segurança;
- nenhum incidente de privacidade;
- nenhum scope breach;
- pelo menos quatro evidências;
- infraestrutura mensal projetada dentro do teto global de R$200.

Cada escolha ainda possui pré-condições próprias, como plano de offboarding,
remediação, capacidade, repricing, pausa ou encerramento.

## Resultado máximo

`READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY`

com:

- action_ceremony_eligible=true;
- owner_action_signature_required=true.

Ainda ficam falsos:

- action_request_issued;
- owner_action_signature_verified;
- business_action_authorized;
- renewal_authorized;
- expansion_authorized;
- non_renewal_authorized;
- remediation_authorized;
- pause_authorized;
- termination_authorized;
- billing_authorized;
- pricing_change_authorized;
- quota_change_authorized;
- package_change_authorized;
- role_change_authorized;
- integration_change_authorized;
- customer_contact_authorized;
- provisioning_authorized;
- deploy_authorized;
- crm_write_authorized;
- production_mutation_authorized;
- external_action_executed;
- executes_action.

Elegibilidade continua separada de autorização e execução.
