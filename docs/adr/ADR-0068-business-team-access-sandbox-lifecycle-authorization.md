# ADR-0068 — Business Team Access Sandbox Lifecycle Authorization

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0067 define um plano manual de dez etapas, mas o plano por si só não
autoriza mutações no sandbox. É necessário um registro humano explícito,
vinculado ao plano exato e ao baseline que originou esse plano.

## Decisão

Criar um contrato de autorização que valida:

- schema do plano;
- estado de decisão do plano;
- plan digest exato;
- baseline evidence digest exato;
- administrador esperado;
- timestamp com timezone;
- token formal exato;
- todos os acknowledgements;
- sandbox_only=true;
- production_targeted=false;
- secret_material_included=false;
- executor_enabled=false.

Mensagens genéricas não contam como autorização.

## Token

AUTHORIZE_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST

## Acknowledgements obrigatórios

- SANDBOX_ONLY;
- NO_PRODUCTION_TARGETS;
- TEST_IDENTITY_ONLY;
- SECRETS_STAY_LOCAL;
- MANUAL_STEP_BY_STEP_APPLY;
- STOP_ON_FIRST_MISMATCH;
- REVOCATION_AND_CLEANUP_REQUIRED.

## Efeito de um registro validado

Um registro válido pode provar que o administrador autorizou o lifecycle manual
do sandbox vinculado àquele plano.

Ele não:
- habilita executor;
- executa comando;
- cria conta;
- habilita MFA;
- grava registry;
- revoga sessão;
- autoriza produção;
- autoriza deploy;
- autoriza runtime.

Qualquer drift no plan digest ou baseline digest invalida o binding.

## Compatibilidade

Complementa ADR-0048 e ADR-0063 até ADR-0067.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
