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

Average Daily Range e American Depositary Receipts não têm arquivo aqui. Seu estado de produto está na reconciliação `CHECKPOINT_MESTRE_RECONCILIATION_2026_09_15_TO_2026_09_29`.
