# AION V2.25 — Explicit Owner Decision Record

## Objetivo

V2.25 registra uma decisão explícita do HUMAN_OWNER somente depois de duas provas
criptográficas distintas:

1. assinatura V2.24 sobre identidade + estado exato;
2. assinatura V2.25 sobre a escolha exata do proprietário.

As únicas escolhas aceitas são:

- `APPROVE_CORE_FREEZE`;
- `DENY_CORE_FREEZE`.

Nenhum alias, abreviação, booleano ou texto de chat é convertido em decisão.

## Por que existe uma segunda assinatura

A assinatura V2.24 prova que o proprietário:

- controla uma chave autorizada;
- reconheceu o estado V2.23 exato.

Ela não contém a escolha APPROVE/DENY.

Por isso V2.25 não aceita um campo `decision` fornecido isoladamente. Ela cria um
novo request de decisão e exige uma assinatura externa específica sobre esse request.

## Binding da decisão

O request V2.25 inclui:

- HUMAN_OWNER;
- tenant;
- propósito fixo de decisão;
- escolha exata APPROVE/DENY;
- target commit SHA;
- digest do request V2.24;
- digest da assinatura V2.24;
- digest assinável V2.23;
- identidade da chave usada em V2.24;
- fingerprint da chave V2.24;
- identidade da chave usada para a decisão;
- fingerprint da chave de decisão;
- ceremony id;
- nonce próprio;
- issued_at/expires_at;
- todas as flags de execução congeladas em false.

O request é reconstruído do estado atual antes de verificar a assinatura de decisão.

## Resultado APPROVE

Assinatura válida de `APPROVE_CORE_FREEZE` produz:

`OWNER_DECISION_RECORDED_APPROVE`

e registra:

- `owner_decision_recorded=true`;
- `owner_decision=APPROVE_CORE_FREEZE`;
- `core_freeze_approved=true`;
- `requires_separate_core_freeze_ceremony=true`.

Mas continua obrigatoriamente:

- `core_freeze_execution_authorized=false`;
- `core_freeze_authorized=false`;
- `core_frozen=false`;
- `execution_allowed=false`;
- `worker_armed=false`;
- `merge_authorized=false`;
- `deploy_authorized=false`.

Ou seja: APPROVE autoriza somente avançar para uma futura cerimônia separada de
Core Freeze. Não executa freeze.

## Resultado DENY

Assinatura válida de `DENY_CORE_FREEZE` produz:

`OWNER_DECISION_RECORDED_DENY`

e registra:

- `core_freeze_approved=false`;
- `core_freeze_denied=true`;
- `requires_separate_core_freeze_ceremony=false`.

Nenhum caminho de freeze deve prosseguir a partir de DENY.

## Replay protection

A decisão usa nonce durável próprio em `PersistentNonceRegistry`.

O escopo prende:

- HUMAN_OWNER;
- tenant;
- target SHA;
- request V2.24;
- chave da decisão.

Um nonce de decisão consumido não pode ser reutilizado.

Falha do registry é fail-closed.

## Janela temporal

A janela máxima é de 180 segundos.

Decisão futura, expirada, com janela inválida ou longa demais é bloqueada.

## Texto de chat continua não sendo decisão

Mesmo que o usuário escreva:

- "vamos lá";
- "continua";
- "pode seguir";
- "aprovado";
- "ok";

isso não satisfaz V2.25.

O registro exige uma assinatura Ed25519 válida sobre um request contendo uma das duas
escolhas canônicas.

## Checkpoint Mestre

Após uma decisão V2.25 válida, o módulo pode gerar somente um **patch candidate**
lógico:

`aion_core_owner_decision`

Esse patch ainda exige persistência explícita posterior.

V2.25 não chama save e não modifica o runtime.

## Estado real atual

O runtime oficial ainda não possui attestation real V2.23 nem assinatura real V2.24.

Logo:

- não existe request real V2.25;
- não existe decisão real APPROVE;
- não existe decisão real DENY.

CI valida o mecanismo com chaves efêmeras sintéticas.

## Próxima fronteira

Somente depois de:

1. attestation real V2.23;
2. assinatura real V2.24;
3. assinatura real da decisão V2.25;
4. persistência explícita do decision record;

uma camada posterior poderá preparar a cerimônia de Core Freeze.

Mesmo então, freeze deve continuar separado de merge/deploy e de ativação do Worker.
