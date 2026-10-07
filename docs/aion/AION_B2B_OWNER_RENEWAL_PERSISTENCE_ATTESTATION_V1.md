# AION B2B — Owner Renewal Persistence Attestation V1

Status: **staging / verification only / no storage write**.

## Objetivo

Comprovar que a decisão de renovação/continuidade, já assinada e verificada, foi
persistida exatamente no Checkpoint Mestre esperado por uma rota externa de
persistência.

Este módulo não grava o checkpoint.

## Verificações

A atestação valida:

- integridade do checkpoint anterior;
- revisão e state digest esperados;
- namespace exato;
- event ID determinístico;
- patch digest;
- decision record digest;
- customer e pilot;
- escolha exata;
- checkpoint observado depois da gravação;
- último evento do journal;
- snapshot reconstruído;
- digest do checkpoint antes/depois;
- receipt externo;
- freshness máxima de 300 segundos.

O checkpoint esperado é calculado com `append_checkpoint_patch(...)` apenas em
memória para comparação.

## Writer boundary

V1 comprova consistência do receipt, mas não prova criptograficamente a
identidade do writer:

`writer_identity_verified=false`.

Um receipt tentando afirmar `writer_identity_verified=true` é rejeitado.

## Resultado máximo

`OWNER_RENEWAL_DECISION_PERSISTENCE_ATTESTED`

Nesse ponto:

- owner_decision_recorded=true;
- decision_persisted=true;
- persistence_attested=true;
- receipt_consistency_verified=true;
- eligible_for_action_preflight=true.

Elegibilidade para preflight **não é autorização**.

## Autoridade continua bloqueada

Mesmo após a persistência atestada continuam falsos:

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

## Próxima fronteira

A próxima camada pode avaliar um action preflight específico para a escolha
persistida, ainda sem executar a ação.
