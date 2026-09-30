# ADR-0082 — Business Team Access Step 1 Ledger Append Decision Contract

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0081 valida o provider receipt e prova em memória que o ledger resultaria
em 1/10 concluído. Esse preview ainda não é autorização para persistir o append.

## Decisão

Criar um contrato explícito e não executável para a decisão de append do receipt
canônico do Step 1.

A request fica presa a:

- receipt_review_digest;
- canonical receipt digest;
- source ledger digest;
- target ledger preview digest;
- administrador esperado;
- token exato.

A source ledger precisa continuar no estado GENESIS/0 receipts. O target precisa
representar exatamente 1/10 concluído com Step 2 como next expected.

## Token

O token é derivado integralmente de:

APPEND_SANDBOX_STEP1_LEDGER_<receipt_review_digest>_<source_ledger_digest>_<target_ledger_digest>

Mensagens genéricas não autorizam append.

## Acknowledgements

- RECEIPT_REVIEW_DIGEST_VERIFIED;
- SOURCE_LEDGER_GENESIS_VERIFIED;
- CANONICAL_RECEIPT_VERIFIED;
- TARGET_LEDGER_PREVIEW_VERIFIED;
- NO_AUTOMATIC_APPEND;
- STEP2_SEPARATE_AUTHORIZATION_REQUIRED.

## Estado máximo

EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED

Esse estado autoriza somente uma futura operação manual de append vinculada aos
digests exatos.

## Segurança

O contrato:
- não grava ledger;
- não executa append;
- não autoriza Step 2;
- não habilita executor;
- não autoriza produção/deploy/runtime.

## Compatibilidade

Complementa ADR-0069 e ADR-0081.
