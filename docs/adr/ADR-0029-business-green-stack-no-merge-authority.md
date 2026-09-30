# ADR-0029 — Stack verde #394–#412 não concede autoridade de merge

- Título: Stack verde #394–#412 não concede autoridade de merge
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Core e o AION Business evoluíram em uma stack linear de Draft PRs que
agora cobre hardening, certificação, sandbox, experiência comercial, governança,
readiness e primeiro piloto controlado.

## Problema

Uma sequência longa de PRs verdes pode ser confundida com autorização implícita
para merge, deploy ou runtime.

Também é necessário preservar uma ordem técnica e um plano de parada caso uma
consolidação futura revele regressão.

## Decisão

Congelar a stack #394–#412 em um manifest administrativo com:

- PR;
- base;
- head branch;
- HEAD SHA;
- estado open/draft;
- mergeability;
- checks;
- ordem técnica;
- bundle digest;
- plano de rollback de integração.

O estado máximo produzido automaticamente é `READY_FOR_ADMIN_REVIEW`.

Qualquer merge continua dependendo de autorização administrativa explícita.

## Consequências

A equipe pode revisar a stack inteira como um pacote, detectar drift e saber
exatamente qual ordem seria usada, sem executar nenhuma ação irreversível.

## Segurança

O módulo não faz merge, rebase, deploy, publicação, pagamento, piloto ou
ativação de runtime.

## Compatibilidade

ADR-0028 define a governança do primeiro piloto. Este ADR governa a consolidação
administrativa da stack que antecede qualquer etapa operacional.

## Rollback

O próprio módulo é read-only. O plano de rollback descrito nele só passa a ser
aplicável após uma futura autorização de merge.

## Supersedes

ADR-0028-business-green-stack-no-merge-authority da PR #413, que ficou
superseded antes de merge por não incluir a #412 e por colidir na numeração.

## Superseded by

Nenhum.
