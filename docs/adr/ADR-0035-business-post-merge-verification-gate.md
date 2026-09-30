# ADR-0035 — Cada merge futuro exige verificação pós-etapa antes do próximo preflight

- Título: Cada merge futuro exige verificação pós-etapa antes do próximo preflight
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A consolidação Business já possui revisão, autorização explícita, preflight e
dossiê de execução. Uma futura execução física ainda precisa de uma barreira
depois de cada merge para impedir continuidade sobre uma main regressiva.

## Decisão

Adicionar um verificador pós-merge read-only. Sem evidência real de merge, o
estado é `POST_MERGE_EVIDENCE_REQUIRED`.

Após uma execução futura separadamente autorizada, o verificador exige:

- SHA observado da main igual ao SHA esperado do resultado;
- SHA novo diferente da main pré-merge;
- referência de rollback igual à main pré-merge;
- Quality Tests verde;
- Release Readiness verde;
- AION Core Security Gate verde;
- UI Smoke verde;
- Mobile DOM verde;
- BUSINESS runtime OFF;
- ausência de autoridade de deploy;
- referência de evidência.

## Estados

- `POST_MERGE_EVIDENCE_REQUIRED`: nenhum resultado real suficiente;
- `STEP_VERIFIED_FOR_NEXT_PREFLIGHT`: etapa íntegra para construir o próximo preflight;
- `ROLLBACK_REVIEW_REQUIRED`: drift ou regressão exige revisão humana.

## Rollback

O sistema prepara apenas um pacote de revisão. Rollback automático permanece
proibido e `rollback_execution_authorized=false`.

## Segurança

Sem merge, rollback, rebase, auto-merge, deploy, piloto, publicação, cobrança
ou ativação de runtime.

## Compatibilidade

ADR-0033 define o preflight e ADR-0034 o dossiê humano. Este ADR fecha o ciclo
com a validação pós-etapa antes de permitir o próximo preflight.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
