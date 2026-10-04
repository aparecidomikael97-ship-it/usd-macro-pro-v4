# AION V2.24 — Owner Signature Ceremony / Signature Verification

## Objetivo

V2.24 cria a primeira camada que consegue verificar uma **assinatura explícita do
proprietário** sobre o estado exato validado pela V2.23.

Ela mantém três coisas separadas:

1. identidade/assinatura do proprietário;
2. decisão do proprietário;
3. Core Freeze/execução.

Uma não implica automaticamente a outra.

## Pré-requisito

V2.24 só prepara request assinável se a V2.23 puder ser reconstruída como:

`READY_FOR_OWNER_SIGNATURE_CEREMONY`

Ou seja, a persistência externa precisa estar realmente atestada.

No estado real atual, isso ainda não aconteceu, porque o runtime oficial não contém o
binding V2.23.

CI utiliza evidência sintética/controlada para validar o mecanismo; isso não cria uma
assinatura real nem uma attestation real.

## Trust root separado do proprietário

A assinatura do proprietário usa um `TrustRootRegistry` separado, contendo somente
chaves públicas de verificação autorizadas para o HUMAN_OWNER.

A V2.24:

- nunca cria chave secreta;
- nunca lê chave secreta;
- nunca armazena chave secreta;
- nunca exporta chave secreta;
- usa somente chave pública para verificação.

A implementação atual verifica assinatura externa **Ed25519**.

Windows Hello/FIDO2 permanecem como adaptadores futuros. V2.24 não captura biometria e
não finge que uma integração de plataforma já existe.

## Request de assinatura

O request é reconstruído diretamente da evidência V2.23 e inclui:

- ceremony id;
- HUMAN_OWNER;
- tenant `atlasquant-owner`;
- propósito fixo `OWNER_IDENTITY_AND_STATE_ACKNOWLEDGEMENT`;
- mecanismo `ED25519_EXTERNAL_OWNER_KEY`;
- target commit SHA;
- digest assinável V2.23;
- runtime SHA;
- runtime checkpoint digest;
- runtime binding digest;
- challenge digest V2.22;
- janela temporal curta;
- nonce;
- key id/version;
- decisão ainda `UNDECIDED`;
- flags críticas falsas.

O digest exposto ao assinante é derivado do request inteiro.

## Assinatura não é aprovação

O propósito da assinatura V2.24 é provar:

- controle da chave pública autorizada do proprietário;
- ciência do estado exato que está sendo apresentado;
- vínculo com o estado persistido e atestado.

Ela **não** contém `APPROVE_CORE_FREEZE`.

Após assinatura válida, o máximo é:

`READY_FOR_EXPLICIT_OWNER_DECISION`

Nesse estado:

- `owner_signature_verified=true`;
- `owner_identity_verified=true`;
- `state_binding_verified=true`;
- `owner_decision_ready=true`;
- `owner_decision=UNDECIDED`;
- `approval_implied=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `execution_allowed=false`;
- `worker_armed=false`.

A decisão APROVAR/NEGAR permanece para uma camada posterior.

## Replay protection

Nonce é registrado em `PersistentNonceRegistry` somente depois de:

- reconstrução V2.23 bem-sucedida;
- request atual idêntico ao reconstruído;
- chave ativa e não revogada;
- assinatura criptográfica válida.

O mesmo nonce não pode ser usado novamente no escopo do proprietário/chave.

Falha do nonce registry é fail-closed.

## Janela temporal

A janela máxima do request é de 180 segundos.

Request:

- futuro;
- expirado;
- com janela zero/negativa;
- com janela maior que 180 segundos

é bloqueado.

V2.23 também é reconstruída no momento da verificação. Portanto o runtime precisa
continuar fresco.

## Texto de chat não é assinatura

Frases como:

- "vamos lá";
- "continua";
- "pode seguir";
- "ok";
- "autorizado"

não são material criptográfico e nunca satisfazem V2.24.

O verificador exige 64 bytes de assinatura Ed25519 válida contra o trust root do
proprietário.

## Ações proibidas nesta camada

V2.24 não:

- captura assinatura;
- captura Windows Hello;
- captura FIDO2;
- grava decisão;
- salva Checkpoint;
- congela Core;
- mergeia;
- deploya;
- arma Worker;
- executa ação externa.

## Estado real em 04/10/2026

Como o runtime oficial ainda não possui attestation V2.23 real, não existe request
V2.24 real pronto para assinatura.

A CI valida somente o mecanismo com chaves efêmeras sintéticas dentro dos testes.

## Próxima fronteira

Após uma futura attestation real V2.23 e uma assinatura real V2.24, a próxima camada
poderá registrar uma decisão explícita `APPROVE` ou `DENY`, ligada à assinatura.

Mesmo uma decisão `APPROVE` não deverá executar Core Freeze automaticamente.
