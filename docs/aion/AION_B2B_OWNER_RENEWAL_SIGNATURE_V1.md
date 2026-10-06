# AION B2B — Owner Renewal Signature V1

Status: **staging / cryptographic verification / no execution**.

## Objetivo

Verificar uma assinatura externa Ed25519 do proprietário sobre a escolha exata
preparada pelo Owner Renewal Decision Request.

A assinatura vincula:

- owner;
- tenant;
- workspace;
- customer;
- pilot;
- pacote;
- tipo de revisão;
- escolha exata;
- digest do pacote de revisão;
- digest do ciclo recorrente;
- digest do contrato;
- digest da conversão value-bound;
- digest da solicitação anterior;
- ceremony ID;
- nonce;
- janela curta de validade;
- key ID / versão / fingerprint.

## Proteções

A cerimônia:

- exige chave pública ativa no Trust Root;
- valida janela máxima de 180 segundos;
- verifica Ed25519;
- protege replay com PersistentNonceRegistry;
- reconstrói a solicitação anterior e falha se o pacote de revisão mudou;
- bloqueia qualquer flag de autoridade alterada;
- não aceita mensagem genérica de chat como decisão.

## Resultado válido

Uma assinatura correta produz somente:

`OWNER_RENEWAL_DECISION_VERIFIED_PENDING_PERSISTENCE`

Isto significa que a escolha foi criptograficamente verificada, mas ainda:

- não foi registrada como decisão persistida;
- não renovou;
- não expandiu;
- não pausou;
- não encerrou;
- não cobrou;
- não alterou preço;
- não alterou quota;
- não alterou pacote/roles/integrações;
- não contatou cliente;
- não provisionou;
- não escreveu CRM;
- não chamou provider;
- não fez deploy;
- não alterou produção.

## Próxima fronteira

Persistência da decisão deve ser outro estágio explícito, com prova do checkpoint
exato e sem confundir persistência com autorização de execução.
