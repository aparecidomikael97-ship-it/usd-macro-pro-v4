# ADR-0024 — Decisão do proprietário é separada da execução do Core Freeze

- Título: Decisão do proprietário é separada da execução do Core Freeze
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

V2.24 verifica identidade e ciência do estado, mas deliberadamente deixa
`owner_decision=UNDECIDED`.

Uma decisão real precisa escolher APPROVE ou DENY de forma explícita e auditável.

## Problema

Seria inseguro:

- tratar a assinatura V2.24 como aprovação implícita;
- aceitar `decision=APPROVE` sem assinatura específica;
- interpretar texto comum de chat como decisão crítica;
- permitir replay da mesma decisão;
- transformar APPROVE diretamente em freeze;
- permitir que decisão abra merge/deploy/arming automaticamente.

## Alternativas rejeitadas

- uma única assinatura para identidade + decisão;
- decisão por booleano;
- decisão por texto livre;
- aliases como YES/OK/APPROVE;
- decisão sem nonce durável;
- decisão sem reconstruir V2.24/V2.23;
- APPROVE executando Core Freeze automaticamente;
- persistência automática do registro de decisão.

## Decisão

V2.25 aceita somente:

- `APPROVE_CORE_FREEZE`;
- `DENY_CORE_FREEZE`.

A escolha recebe um request próprio e assinatura externa própria.

O request prende a decisão à assinatura V2.24 e ao estado V2.23 atual. Uma assinatura
válida comprova a escolha, mas o decision record permanece pendente de persistência e
attestation.

## Semântica de APPROVE

APPROVE significa somente:

- escolha do proprietário criptograficamente verificada;
- record lógico preparado para persistência.

Enquanto a persistência do decision record não for atestada,
`owner_decision_recorded=false` e a cerimônia de Core Freeze não fica elegível.

APPROVE não significa:

- Core congelado;
- freeze execution autorizado;
- merge autorizado;
- deploy autorizado;
- Worker armado;
- execução externa.

## Semântica de DENY

DENY comprova a escolha de negar e prepara seu record para persistência. O caminho
de Core Freeze permanece fechado; persistir/atestar o DENY fornece o registro durável
da negativa.

Qualquer nova tentativa exige novo estado/cerimônia conforme contratos aplicáveis.

## Segurança

V2.25 exige:

- V2.24 reconstruída e assinatura de identidade válida;
- decisão canônica;
- assinatura específica da decisão;
- chave ativa/não revogada;
- fingerprints exatos;
- janela temporal máxima de 180s;
- nonce persistente anti-replay;
- request reconstruído idêntico ao apresentado.

## Checkpoint

A camada gera o patch candidate somente dentro do fluxo que acabou de verificar
criptograficamente a assinatura da decisão. Um caller não pode fornecer um
dicionário de "verified decision" como autoridade.

Persistência e attestation do decision record continuam separadas e explícitas.
Somente depois delas a decisão pode ser chamada de registrada de forma durável.

## Compatibilidade

Compõe ADR-0002, ADR-0007, ADR-0009, ADR-0011, ADR-0012, ADR-0019, ADR-0020,
ADR-0021, ADR-0022 e ADR-0023.

## PR/commit relacionado

Branch `integration/aion-v225-explicit-owner-decision-record-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
