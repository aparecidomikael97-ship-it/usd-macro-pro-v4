# ADR-0073 — Business Team Access Sandbox Baseline Acceptance

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

Um handoff técnico coerente prova que readiness e baseline pertencem à mesma
sessão local. Isso ainda não significa que o administrador aceitou aquele
baseline como entrada do lifecycle.

## Decisão

Criar um registro explícito de aceitação do baseline, vinculado a:

- handoff digest;
- baseline evidence digest;
- readiness digest;
- operator session id;
- administrador esperado;
- timestamp com timezone;
- token formal;
- acknowledgements completos.

## Token

ACCEPT_TEAM_ACCESS_SANDBOX_BASELINE

## Acknowledgements

- SAME_OPERATOR_SESSION;
- BASELINE_READ_ONLY_EVIDENCE;
- HANDOFF_DIGEST_BOUND;
- BASELINE_DIGEST_BOUND;
- NO_LIFECYCLE_EXECUTION;
- NO_PRODUCTION_TARGETS.

Mensagens genéricas não são aceitação.

## Efeito

Um registro validado pode autorizar apenas o uso daquele baseline como entrada
do builder de lifecycle.

Ele não:
- cria lifecycle plan automaticamente;
- autoriza lifecycle execution;
- cria conta;
- habilita MFA;
- grava registry;
- revoga sessão;
- autoriza produção/deploy/runtime.

## Hardening do builder

build_lifecycle_test_plan passa a exigir um baseline acceptance binding válido.
Um baseline tecnicamente verde sem aceitação explícita é bloqueado.

## Compatibilidade

Complementa ADR-0066, ADR-0072 e ADR-0067 até ADR-0070.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
