# BUSINESS Post-Merge Verification & Rollback Gate V1 — 2026-09-30

## Missão

Garantir que uma futura consolidação física nunca avance para a próxima PR sem
validar o resultado da etapa anterior.

## Sem merge real

O estado permanece `POST_MERGE_EVIDENCE_REQUIRED`.

## Evidência obrigatória após merge futuro

- SHA esperado e SHA observado;
- main pré-merge;
- rollback reference;
- Quality;
- Readiness;
- Security;
- UI Smoke;
- Mobile DOM;
- BUSINESS runtime OFF;
- deploy authority ausente;
- referência de evidência.

## Resultado verde

`STEP_VERIFIED_FOR_NEXT_PREFLIGHT`.

Isso só permite montar o próximo preflight. Não autoriza novo merge.

## Resultado regressivo

`ROLLBACK_REVIEW_REQUIRED`.

O sistema prepara revisão humana, mas não executa rollback.

## Segurança

Sem merge, rollback automático, rebase, auto-merge, deploy, piloto, cliente
real, publicação, cobrança ou runtime.
