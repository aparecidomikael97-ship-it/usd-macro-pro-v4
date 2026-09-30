# Architecture Decision Records

ADR, neste diretório, significa **Architecture Decision Records**.

O registry pertence ao AION Núcleo / Developer. Ele passa a proteger decisões estruturais durante o fechamento do Núcleo. Os arquivos são versionados no Git. Não há banco próprio.

Um ADR substituído não é apagado. O status muda para `SUPERSEDED` ou `DEPRECATED`, e `Superseded by` aponta o sucessor.

## Três significados que não podem ser misturados

| Sigla | Significado | Local | Neste registry |
| --- | --- | --- | --- |
| ADR | Architecture Decision Records | AION Núcleo / Developer | Sim. Este diretório. |
| ADR | Average Daily Range | AION Trader Expert, futuro | Não. Fica no roadmap como APROVADO / PENDENTE. |
| ADR | American Depositary Receipts | AION Investment Expert, futuro | Não. Fica no roadmap como APROVADO / PENDENTE. |

ATR significa **Average True Range**. É outro indicador, também futuro no AION Trader Expert, e não substitui nenhum dos três significados acima.

## Estados

`PROPOSED`, `ACCEPTED`, `SUPERSEDED`, `DEPRECATED`, `REJECTED`.

## Formato

Cada registro usa o identificador `ADR-NNNN` e as seções: Título, Data, Status, Contexto, Problema, Alternativas consideradas, Decisão, Consequências, Componentes afetados, Segurança, Compatibilidade, Rollback/migração, PR/commit relacionado, Supersedes e Superseded by.

## Registry

| ID | Status | Arquivo |
| --- | --- | --- |
| ADR-0001 | ACCEPTED | `docs/adr/ADR-0001-aion-nucleo-central-especialistas.md` |
| ADR-0002 | ACCEPTED | `docs/adr/ADR-0002-aprovacao-humana-alto-impacto.md` |
| ADR-0003 | ACCEPTED | `docs/adr/ADR-0003-evidencia-incompleta-nao-confirmada.md` |
| ADR-0004 | ACCEPTED | `docs/adr/ADR-0004-separacao-admin-user.md` |
| ADR-0005 | ACCEPTED | `docs/adr/ADR-0005-especialistas-sem-permissao-independente.md` |
| ADR-0006 | ACCEPTED | `docs/adr/ADR-0006-definition-of-done-human-release-review.md` |
| ADR-0007 | ACCEPTED | `docs/adr/ADR-0007-checkpoint-mestre-persistencia-oficial.md` |
| ADR-0008 | ACCEPTED | `docs/adr/ADR-0008-real-trading-fail-closed.md` |
| ADR-0009 | ACCEPTED | `docs/adr/ADR-0009-release-deploy-merge-gate.md` |
| ADR-0010 | ACCEPTED | `docs/adr/ADR-0010-quatro-fechamentos-do-aion.md` |\n| ADR-0011 | ACCEPTED | `docs/adr/ADR-0011-core-validation-business-readiness.md` |\n| ADR-0012 | ACCEPTED | `docs/adr/ADR-0012-business-primary-scope-certification.md` |
| ADR-0013 | ACCEPTED | `docs/adr/ADR-0013-business-external-attestation-review.md` |
| ADR-0014 | ACCEPTED | `docs/adr/ADR-0014-business-runtime-readiness.md` |
| ADR-0015 | ACCEPTED | `docs/adr/ADR-0015-business-sandbox-harness.md` |
| ADR-0016 | ACCEPTED | `docs/adr/ADR-0016-business-demo-simple-experience.md` |
| ADR-0017 | ACCEPTED | `docs/adr/ADR-0017-business-admin-training-before-live.md` |
| ADR-0018 | ACCEPTED | `docs/adr/ADR-0018-business-diagnostic-proposal-simulator.md` |
| ADR-0019 | ACCEPTED | `docs/adr/ADR-0019-business-client-portal-simple-truth.md` |
| ADR-0020 | ACCEPTED | `docs/adr/ADR-0020-business-sandbox-first-onboarding.md` |
| ADR-0021 | ACCEPTED | `docs/adr/ADR-0021-business-customer-success-before-upsell.md` |
| ADR-0022 | ACCEPTED | `docs/adr/ADR-0022-business-client-finance-capacity.md` |
| ADR-0023 | ACCEPTED | `docs/adr/ADR-0023-business-trends-evidence-improvement.md` |
| ADR-0024 | ACCEPTED | `docs/adr/ADR-0024-business-diagnostic-first-commercial-flow.md` |
| ADR-0025 | ACCEPTED | `docs/adr/ADR-0025-business-integration-hub-least-privilege.md` |
| ADR-0026 | ACCEPTED | `docs/adr/ADR-0026-business-privacy-default-deny-audit.md` |
| ADR-0027 | ACCEPTED | `docs/adr/ADR-0027-business-demo-pilot-live-authority.md` |

Average Daily Range e American Depositary Receipts não têm arquivo aqui. Seu estado de produto está na reconciliação `CHECKPOINT_MESTRE_RECONCILIATION_2026_09_15_TO_2026_09_29`.

| ADR-0028 | ACCEPTED | `docs/adr/ADR-0028-business-bounded-first-pilot.md` |
| ADR-0029 | ACCEPTED | `docs/adr/ADR-0029-business-green-stack-no-merge-authority.md` |
| ADR-0030 | ACCEPTED | `docs/adr/ADR-0030-business-live-revalidation-before-consolidation.md` |
| ADR-0031 | ACCEPTED | `docs/adr/ADR-0031-business-consolidation-decision-binding.md` |
| ADR-0032 | ACCEPTED | `docs/adr/ADR-0032-business-explicit-consolidation-authorization-record.md` |
| ADR-0033 | ACCEPTED | `docs/adr/ADR-0033-business-consolidation-execution-preflight.md` |
| ADR-0034 | ACCEPTED | `docs/adr/ADR-0034-business-execution-review-packet.md` |
| ADR-0035 | ACCEPTED | `docs/adr/ADR-0035-business-post-merge-verification-gate.md` |
| ADR-0036 | ACCEPTED | `docs/adr/ADR-0036-business-consolidation-progress-ledger.md` |
