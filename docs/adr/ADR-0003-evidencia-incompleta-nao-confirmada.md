# ADR-0003 — Evidência UNKNOWN, STALE ou incompleta não vira fato CONFIRMED

- Título: Evidência UNKNOWN, STALE ou incompleta não vira fato CONFIRMED
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

ARCHITECTURE.md e ADDING_CAPABILITIES.md já rebaixam confirmação sem fonte, dado stale e conflito. A Specialist Session também marca normalização incompleta.

## Problema

Prefixo truncado, string ambígua ou dado velho pode ser apresentado como fato atual.

## Alternativas consideradas

Escolher o primeiro valor disponível foi rejeitado. Fail-closed é a alternativa aceita.

## Decisão

UNKNOWN, STALE, conflito e evidência incompleta não podem virar fato CONFIRMED nem ser usados como fato atual. O leitor não escolhe um lado parcial.

## Consequências

Contratos locais de verdade e de sessão já existem e seguem em validação. Esta ADR não declara o ecossistema inteiro validado.

## Componentes afetados

atlasquant_aion_truth.py; atlasquant_aion_specialist_session.py; leituras de especialista.

## Segurança

Incompletude não libera ordem, publicação ou resposta confirmada ao usuário.

## Compatibilidade

Estados ABSENT, STALE, CONFLICTING, VALID e UNVERIFIED permanecem. INCOMPLETE não é promovido a VALID.

## Rollback/migração

Não apagar o registro se um leitor futuro passar a tolerar truncamento. Substituir por ADR novo.

## PR/commit relacionado

Evidência de código no SHA base 996d97b58bd6a56a9592dab43da99dd4bfd35e1d, sem atribuir deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
