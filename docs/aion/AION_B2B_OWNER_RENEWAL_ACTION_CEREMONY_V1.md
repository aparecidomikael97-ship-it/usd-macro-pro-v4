# AION B2B — Owner Renewal Action Ceremony V1

Status: **staging / cryptographic owner intent / pending persistence / no execution**.

## Objetivo

Transformar um preflight recorrente limpo em uma decisão explícita e
criptograficamente verificável do proprietário.

As únicas decisões aceitas são:

- AUTHORIZE_BUSINESS_ACTION;
- DENY_BUSINESS_ACTION.

Uma mensagem genérica de chat, inclusive "vamos lá", não é uma decisão válida.

## Binding

A assinatura Ed25519 fica presa a:

- owner / tenant / workspace;
- customer / pilot / package;
- review type;
- escolha comercial previamente persistida;
- action family;
- digest da revisão;
- digest do ciclo;
- digest do contrato;
- digest da conversão value-bound;
- decision-record digest;
- persistence receipt digest;
- checkpoint digest;
- writer-request digest;
- environment digest;
- preflight digest;
- ceremony ID;
- nonce;
- janela curta;
- key ID/version/fingerprint.

## Proteções

- Trust Root ativo obrigatório;
- janela máxima de 180 segundos;
- replay protection durável;
- reconstrução exata do request;
- preflight alterado depois da preparação bloqueia;
- qualquer autoridade já presente no preflight bloqueia.

## Resultado máximo

Uma assinatura válida de autorização produz apenas:

`OWNER_BUSINESS_ACTION_DECISION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE`.

Uma assinatura válida de negação produz:

`OWNER_BUSINESS_ACTION_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE`.

No caso de autorização:

- action_authorization_intent=true;
- action_record_persisted=false;
- business_action_authorized=false.

Portanto, a assinatura comprova a intenção, mas ainda não torna a ação executável.

## Autoridade permanece bloqueada

Mesmo com assinatura válida continuam falsos:

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

A próxima fronteira é persistir e atestar esse registro de autorização, ainda
separado da execução comercial.
