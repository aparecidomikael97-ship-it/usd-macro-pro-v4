# AION FinOps — Ledger Persistence & Invoice Reconciliation V1

## Objetivo

Dar continuidade verificável às versões do ledger e conferir faturas antes de
qualquer pagamento.

## Manifesto de versão

Cada manifesto inclui:
- version_number;
- previous_version_manifest_digest;
- storage_ref;
- created_at;
- created_by;
- ledger_digest;
- ledger_tail_digest;
- ledger_entry_count;
- version_manifest_digest.

## Chain

A primeira versão aponta para `GENESIS_DIGEST`.

Versões seguintes obrigatoriamente apontam para o digest da versão anterior.

Bloqueios:
- gap de versão;
- reorder;
- replay;
- alteração de conteúdo;
- previous digest incorreto.

## Invoice attestation

A fatura precisa ter:
- provider_ref;
- invoice_ref;
- source_ref;
- período;
- total BRL;
- autenticação read-only verificada;
- integridade da fonte verificada;
- observed_at.

## Reconciliação

A fatura só reconcilia quando:
- o ledger é válido;
- existem entradas do mesmo provider/período;
- a soma bate dentro da tolerância definida.

Reconciliação não é pagamento.

## Persistência física

O módulo produz `LEDGER_VERSION_MANIFEST_READY`, mas:
- não grava banco;
- não escreve bucket;
- não cria objeto externo;
- não confirma persistência.

O storage real precisa de integração e autorização separadas.

## Autoridade

O máximo é:
`READY_FOR_ADMIN_PERSISTENCE_RECONCILIATION_REVIEW`.

Pagamento, alteração de assinatura e mudança de preço continuam bloqueados.
