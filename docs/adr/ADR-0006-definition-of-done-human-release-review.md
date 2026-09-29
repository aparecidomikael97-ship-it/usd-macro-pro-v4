# ADR-0006 — Definition of Done termina em HUMAN_RELEASE_REVIEW

- Título: Definition of Done termina em HUMAN_RELEASE_REVIEW
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

O Developer Engine documentado em ARCHITECTURE.md termina o fluxo em revisão humana. O código de definition_of_done grava HUMAN_RELEASE_REVIEW quando o conjunto está completo.

## Problema

Uma suíte verde pode ser lida como merge ou deploy autorizado.

## Alternativas consideradas

Fechar o ciclo em merge automático foi rejeitado. A alternativa aceita é parar em revisão humana.

## Decisão

Definition of Done termina em HUMAN_RELEASE_REVIEW. Não significa merge, deploy, publicação ou trading.

## Consequências

O status existe no motor de desenvolvimento e tem teste. Isso não valida um release de produção.

## Componentes afetados

atlasquant_aion_developer_engine.py.

## Segurança

Reviewer permanece distinto do builder. Três tentativas de autocorreção não autorizam promoção.

## Compatibilidade

O estado INCOMPLETE continua disponível quando a evidência não fecha.

## Rollback/migração

Mudar o estado terminal exige ADR novo. Este registro permanece.

## PR/commit relacionado

Evidência local em atlasquant_aion_developer_engine.py e test_atlasquant_aion_developer_engine.py. Sem SHA de produção.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
