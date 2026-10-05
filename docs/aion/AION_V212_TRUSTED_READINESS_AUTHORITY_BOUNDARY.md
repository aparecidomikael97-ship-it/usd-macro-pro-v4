# AION V2.12 — Trusted Readiness Authority Boundary

**Tipo:** contrato fail-closed de autoridade, sem implementação criptográfica real  
**Base:** `614a8e61ae2b270638c4027f3606a6371c185435`  
**Objetivo:** separar definitivamente *readiness* de autoridade confiável.

## Regra central

Nenhum envelope, snapshot, payload, board, health state, consistency state, digest,
checkpoint, memória, aprovação, runtime ou flag booleana fornecida pelo caller pode
criar autoridade de execução.

O V2.12 introduz uma fonte canônica separada:

`trusted_readiness_authority_view()`

Essa fonte ignora qualquer payload recebido e permanece:

- `state=BLOCKED`
- `authority_available=False`
- `authority_verified=False`
- `authority_binding_configured=False`
- `trust_root_configured=False`
- `signature_verification_available=False`
- `execution_authority_granted=False`
- `execution_allowed=False`

## Blockers canônicos

- `TRUSTED_READINESS_AUTHORITY_UNAVAILABLE`
- `TRUST_ROOT_NOT_CONFIGURED`
- `SIGNATURE_VERIFICATION_UNAVAILABLE`
- `AUTHORITY_BINDING_NOT_CONFIGURED`

## Integração com V2.11

O lifecycle V2.11 passa a consumir essa visão canônica. As dimensões presentes no
envelope continuam úteis apenas como claims de readiness local; elas não são
consideradas verificadas por uma autoridade.

Mesmo quando todas as dimensões são `True`, o resultado permanece `BLOCKED`
enquanto a autoridade canônica estiver indisponível.

## O que NÃO está implementado

- nenhuma chave real;
- nenhuma assinatura real;
- nenhum trust root;
- nenhum HSM/KMS;
- nenhum FIDO/WebAuthn;
- nenhum certificado;
- nenhum verifier de produção;
- nenhuma persistência de nonce;
- nenhuma rede;
- nenhuma chamada de provider;
- nenhuma autorização de billing;
- nenhuma ordem real;
- nenhum trading real;
- nenhuma ativação de worker;
- nenhuma relação readiness → approval.

## Condição para evolução futura

Um caminho de `READY` só poderá ser desenhado depois de existir uma origem de
autoridade separada e autenticada, com trust root, verificação de assinatura,
binding de identidade/política, replay protection e política explícita de
rotação/revogação. Até lá, este contrato não possui transição válida para READY.
