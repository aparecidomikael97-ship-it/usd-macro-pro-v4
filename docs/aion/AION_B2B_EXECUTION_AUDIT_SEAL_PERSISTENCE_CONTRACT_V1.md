# AION B2B — Execution Audit Seal Persistence Contract V1

Status: **design-only / fail-closed / non-executable**.

## Objetivo

Definir como o audit seal terminal deverá ser persistido futuramente sem criar
uma segunda verdade ou permitir alteração do fechamento histórico.

Modo:
`APPEND_ONLY_CAS_AUDIT_SEAL_COMMIT`

## Estado máximo

`READY_FOR_EXECUTION_AUDIT_SEAL_PERSISTENCE_DESIGN_REVIEW`

Próximo passo:

`DESIGN_EXECUTION_TERMINAL_CERTIFICATE_CONTRACT_ONLY`

## Persistência futura obrigatória

- execution id canônico;
- terminal revision;
- terminal record já existente;
- expected pre-seal revision;
- compare-and-set;
- single seal winner;
- seal digest único;
- registro append-only e imutável.

## Replay e conflito

Mesmo terminal identity + mesmo seal digest = replay idempotente.

Mesmo terminal identity + seal digest diferente = conflito fail-closed.

Um seal persistido não pode ser apagado, substituído ou usado para reabrir uma
execução terminal.

## Crash/reopen

Crash antes do commit não pode inferir que o seal foi persistido.

Crash depois do commit deve reencontrar exatamente o mesmo seal record, digest,
terminal revision, estado final, algoritmo e canonical encoding.

## Segurança

A persistência do seal não cria autoridade e não autoriza retry, reopen,
reconciliação, rollback, compensação ou efeito externo.

## Esta camada NÃO faz

- abertura de banco/store;
- CAS real;
- escrita do seal;
- geração ou assinatura do seal;
- leitura de private key;
- network/provider query;
- billing/CRM/provisioning/deploy/produção.
