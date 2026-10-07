# AION B2B — Fresh Owner Execution Authorization Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir como um futuro executor deve consumir uma autorização NOVA do Owner,
sem criar um segundo mecanismo de autorização.

A referência obrigatória é a cerimônia já existente:

`atlasquant_aion_b2b_owner_renewal_action_execution_ceremony`

Ela já estabelece:
- Ed25519 externo;
- trust root;
- nonce persistente;
- anti-replay;
- rebuild do request;
- janela máxima de 120 segundos;
- decisão explícita;
- generic chat rejeitado como execução;
- execution intent separado da execução real.

## Estado máximo

`READY_FOR_FRESH_OWNER_EXECUTION_AUTHORIZATION_DESIGN_REVIEW`

Próximo passo permitido:

`DESIGN_RUNTIME_EXECUTION_GUARDS_CONTRACT_ONLY`

## Decisão exigida futuramente

`AUTHORIZE_BUSINESS_ACTION_EXECUTION`

A decisão deve estar ligada ao estado exato e não pode ser reaproveitada de uma
cerimônia anterior.

## Provas obrigatórias

- execution preflight READY;
- human execution confirmation required;
- owner/tenant/workspace exatos;
- customer/pilot/package exatos;
- action family/operation exatos;
- rollback/compensation contract bound;
- authenticated receipt bound;
- idempotency/effect identity bound;
- Ed25519 Owner execution signature;
- active trust-root key;
- public-key fingerprint bound;
- fresh nonce;
- persistent replay rejection;
- <=120s window;
- request rebuild match;
- explicit AUTHORIZE decision;
- execution record persistence;
- persistence attestation;
- writer attestation;
- generic chat rejected;
- single-use authorization.

## Design não equivale a autorização

Esta camada NÃO:
- emite execution request;
- verifica assinatura;
- faz claim de nonce;
- persiste execution record;
- atesta persistence/writer;
- marca authorization verified;
- gera ou executa comando;
- chama provider;
- fatura;
- contacta cliente;
- escreve CRM;
- provisiona;
- deploya;
- toca produção.

"vamos lá", "ok", "continua" e outras mensagens de chat nunca contam como
assinatura ou autorização de execução.
