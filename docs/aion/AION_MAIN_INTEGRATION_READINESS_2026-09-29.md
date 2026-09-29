# AION/Núcleo — Main Integration Readiness — 2026-09-29

Status: **CANDIDATO CONGELADO / NÃO AUTORIZADO PARA MERGE**.

Este documento existe na trilha de handoff, fora da branch candidata, para não alterar o HEAD validado.

## Candidato autoritativo

- PR: **#359**
- Estado: OPEN / DRAFT
- Base: `main`
- Base SHA validado: `2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1`
- Head SHA validado: `a0fa2dff38d2de7e934f3897ecf06dd025552028`
- Mergeable observado: **true**
- Merge autorizado: **não**

A PR temporária #360 usou exatamente o mesmo base SHA e head SHA, foi validada contra `main` e depois encerrada **sem merge**.

## Evidência verde observada para o par base/head acima

- Quality tests — run `36587217829` — **SUCCESS**
  - job `test`
  - 3801 testes — **OK**
- AION Core Security Gate — run `36587217794` — **SUCCESS**
  - `AION adversarial contracts` — SUCCESS
  - `Supply-chain audit` — SUCCESS
- AION Global Worker Activation Readiness — runs `36587220707` e `36587218152` — **SUCCESS**
- AtlasQuant - Release Readiness — run `36587217966` — **SUCCESS**
- AtlasQuant Integration UI Smoke — run `36587217908` — **SUCCESS**
- AtlasQuant - Mobile DOM Stability — run `36587217972` — **SUCCESS**

## Freeze gate

A evidência acima só é válida enquanto **os dois SHAs continuarem iguais**:

- base `main` = `2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1`
- #359 head = `a0fa2dff38d2de7e934f3897ecf06dd025552028`

Se qualquer um mudar, o estado volta para **REVALIDATION_REQUIRED** antes de qualquer decisão de integração.

## Bloqueios deliberados que continuam ativos

Mesmo com CI verde:

- não fazer merge sem aprovação humana explícita;
- não fazer deploy;
- não ativar Global Worker real;
- não habilitar trading real;
- não habilitar provider pago automaticamente;
- não publicar externamente;
- não alterar ruleset/branch protection automaticamente;
- não afirmar multi-instance safety ou 24/7 real sem prova operacional.

## Required checks / ruleset

A proposta está documentada, mas **não foi aplicada**.

- rulesets visíveis na leitura atual: coleção vazia;
- branch protection de `main`: **NOT_VERIFIED** por 403 da integração;
- qualquer mudança administrativa exige autorização explícita e acesso apropriado.

## Interface e plugin

- Interface #358: **PAUSADA pelo usuário**.
- Plugin: **NÃO CRIAR** até pedido explícito do usuário.
- Nenhuma dessas frentes deve alterar o candidato congelado #359.

## Próxima ação segura padrão

Enquanto não houver nova regressão/evidência e não houver autorização administrativa:

1. manter #359 congelada;
2. usar esta trilha de handoff para documentação/auditoria;
3. revalidar somente se base/head mudarem;
4. aguardar decisão humana para ruleset/required checks ou merge.
