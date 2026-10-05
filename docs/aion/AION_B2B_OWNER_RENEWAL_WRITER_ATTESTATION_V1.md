# AION B2B — Owner Renewal Checkpoint Writer Attestation V1

Status: **staging / cryptographic writer verification / no write / no business action**.

## Objetivo

Separar duas provas:

- a persistence attestation prova **o que** foi persistido;
- esta camada prova que uma chave confiável de checkpoint writer reconheceu o
  receipt exato daquela persistência.

Nenhuma das duas camadas realiza a gravação.

## Assinatura

A solicitação Ed25519 vincula:

- receipt digest;
- storage target;
- namespace;
- event ID;
- customer;
- pilot;
- escolha persistida;
- after-checkpoint digest;
- decision-record digest;
- writer reference;
- ceremony ID;
- nonce;
- janela de validade;
- key ID/version/fingerprint.

## Proteções

- TrustRootRegistry obrigatório;
- janela máxima de 180 segundos;
- PersistentNonceRegistry contra replay;
- rebuild exato do request;
- receipt adulterado falha;
- receipt não pode chegar se declarando writer-verificado;
- receipt não pode carregar autoridade comercial.

## Resultado máximo

Uma assinatura válida produz:

`CHECKPOINT_WRITER_AUTHORITY_ATTESTED`

com:

- writer_identity_verified=true;
- writer_authority_verified=true;
- receipt_binding_verified=true;
- nonce_registered=true.

Isso **não** repete a gravação e **não** autoriza a decisão comercial.

Continuam falsos:

- checkpoint_write_performed;
- business_action_authorized;
- renewal_authorized;
- expansion_authorized;
- pause_authorized;
- termination_authorized;
- billing_authorized;
- pricing_change_authorized;
- quota_change_authorized;
- role_change_authorized;
- integration_change_authorized;
- customer_contact_authorized;
- provisioning_authorized;
- deploy_authorized;
- crm_write_authorized;
- production_mutation_authorized;
- external_action_executed;
- executes_action.
