# ADR-0073 — Business Team Access Real Sandbox Baseline Acceptance

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0072 produz um handoff tecnicamente coerente entre readiness e baseline.
Esse handoff ainda não equivale a aceitar o baseline como referência oficial
para o lifecycle.

## Decisão

Adicionar um registro administrativo explícito de aceitação do baseline real.

O registro deve estar vinculado a:

- handoff digest exato;
- baseline evidence digest exato;
- operator_session_id exato;
- administrador que revisou o handoff;
- timestamp com timezone;
- token formal;
- acknowledgements completos.

## Token

ACCEPT_TEAM_ACCESS_REAL_SANDBOX_BASELINE

## Acknowledgements

- SAME_OPERATOR_SESSION_VERIFIED;
- BASELINE_DIGEST_FROZEN;
- SANDBOX_ONLY;
- NO_PRODUCTION_PROMOTION;
- NO_LIFECYCLE_EXECUTION_AUTHORITY;
- SEPARATE_LIFECYCLE_AUTHORIZATION_REQUIRED.

## Estado máximo

REAL_SANDBOX_BASELINE_ACCEPTED_FOR_LIFECYCLE_PLANNING

Esse estado significa somente que o baseline pode ser usado como entrada
congelada para planejamento.

Não significa:
- autorização de lifecycle;
- autorização de step;
- start automático;
- deploy;
- produção;
- runtime.

## Fail-closed

Bloqueiam a aceitação:

- mensagem genérica em vez do token exato;
- digest divergente;
- session id divergente;
- administrador diferente do reviewer;
- timestamp inválido;
- qualquer acknowledgement faltante;
- pedido de promoção para produção;
- pedido de execução do lifecycle.

## Compatibilidade

Complementa ADR-0066, ADR-0071 e ADR-0072.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
