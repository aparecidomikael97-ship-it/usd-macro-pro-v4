# AION B2B — Owner Renewal Action Writer Attestation V1

Status: **staging / writer authority proof / no commercial execution**.

## Objetivo

Comprovar criptograficamente que uma chave confiável do checkpoint writer
reconheceu o receipt exato da persistência da decisão comercial recorrente.

A camada de persistência prova **o que** foi gravado. Esta camada prova **qual
autoridade criptográfica de writer reconheceu aquele receipt**.

## Binding criptográfico

A assinatura Ed25519 prende:

- receipt digest;
- storage target;
- namespace;
- event ID;
- customer;
- pilot;
- escolha comercial;
- action family;
- AUTHORIZE ou DENY;
- after-checkpoint digest;
- action-record digest;
- writer ref;
- ceremony ID;
- nonce;
- key ID/version/fingerprint;
- janela temporal máxima de 180 segundos.

Há replay protection persistente.

## Resultado máximo

`ACTION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED`.

Para AUTHORIZE, o máximo adicional é:

`eligible_for_action_execution_preflight=true`.

Isso só permite que uma camada posterior avalie novamente a situação. Não
autoriza a ação comercial.

Para DENY, essa elegibilidade permanece falsa.

## Autoridade permanece bloqueada

Continuam falsos:

- business_action_authorized;
- renovação;
- expansão;
- não renovação;
- remediação;
- pausa;
- encerramento;
- cobrança;
- repricing;
- alterações de quota/pacote/papéis/integração;
- contato com cliente;
- provisionamento;
- CRM/provider;
- deploy;
- mutação de produção;
- execução externa.

A atestação do writer também não refaz a gravação do checkpoint.
