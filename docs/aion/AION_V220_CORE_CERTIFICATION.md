# AION V2.20 — Core Certification

**Base:** V2.19 head `a2c6da29cc95a4b22706940906f02bbd6860a727`

## Objetivo

Executar a certificação final do AION Core sem confundir certificação com freeze,
merge, deploy ou ativação operacional.

O V2.20 é uma camada de prova.

Ele não adiciona autoridade de execução e não arma o Global Worker.

## Dimensões obrigatórias

A certificação exige evidência independente para:

1. TRUST_ROOT_AUTHORITY
2. DURABLE_EXECUTION
3. CAPABILITY_ISOLATION
4. OPERATIONAL_RESILIENCE
5. MULTIAGENT_MEMORY_GOVERNANCE
6. CONSTITUTION_POLICY_KERNEL
7. PROVIDER_NEUTRAL_MODEL_GATEWAY
8. END_TO_END
9. LOAD
10. CHAOS
11. RECOVERY
12. BACKUP_RESTORE
13. CONCURRENCY
14. COST_GOVERNANCE
15. AUDIT_REPLAY

Nenhuma dimensão ausente é tratada como implícita.

## Evidence row

Cada dimensão deve carregar:

- state = VERIFIED;
- source = CI / TEST_SUITE / DRILL / AUDIT;
- run_id;
- commit_sha exato;
- sha256 evidence digest;
- test_count positivo;
- verified = booleano True exato.

Todas as dimensões precisam apontar para o mesmo target commit da certificação.

## Volume mínimo

A soma de test_count das evidências precisa ser pelo menos 1.000.

Esse número é um piso de integridade do manifesto, não substitui as suites reais.

## Stress sintético V2.20

A suíte dedicada executa, além das verificações do manifesto:

- 5.000 trace contexts;
- 3.000 decisões do provider-neutral model gateway;
- 2.000 decisões do Constitution Policy Kernel;
- 1.000 planos multiagente;
- 1.000 leituras de memória governada;
- 10.000 canonical durable execution IDs.

Essas operações precisam permanecer determinísticas e sem ação externa.

## Suites pesadas reaproveitadas

O workflow de certificação também executa contratos já existentes de:

- chat load: 100 conversations / 1.000 messages / restart / pagination / checkpoint;
- chaos recovery;
- V2.13 trust authority red-team;
- V2.14 durable execution red-team;
- V2.15 capability isolation red-team;
- V2.16 resilience red-team;
- V2.17 multi-agent/memory red-team;
- V2.18 Constitution red-team;
- V2.19 provider-neutral gateway red-team;
- durable task contracts;
- unified journal persistence/recovery;
- tenant privacy/isolation;
- Global Worker recovery drill/readiness contracts.

## Estado de saída

O estado positivo é:

`CERTIFICATION_CANDIDATE`

Isso permite afirmar apenas que o target commit possui as evidências exigidas pelo
contrato de certificação.

Mesmo nesse estado:

- core_frozen = False;
- core_freeze_authorized_by_this_module = False;
- execution_allowed = False;
- worker_armed = False;
- merge_authorized = False;
- deploy_authorized = False;
- external_action_executed = False.

## Core Complete vs Core Freeze

V2.20 separa duas decisões:

### Core Complete

Depois que:
- V2.13–V2.20 estiverem verdes;
- o workflow dedicado de certificação estiver verde;
- todas as dimensões tiverem evidência válida;
- não houver blocker estrutural conhecido;

o head pode se tornar **Core Complete Candidate** para revisão final.

### Core Freeze

O freeze só acontece depois de uma decisão explícita do HUMAN_OWNER.

Nem CI verde, nem certification candidate, nem approval genérico autorizam freeze.

## Relação com Global Worker

Global Worker readiness precisa estar verde como evidência operacional.

Isso não significa:
- worker armado;
- feature flag ligada;
- execução externa;
- trading real.

A certificação nunca arma o worker.

## Falhas

Qualquer falha em:
- canonical gates;
- worker readiness;
- dimensão;
- commit binding;
- evidence digest;
- evidence truth;
- test volume;

mantém estado BLOCKED.

## Critério final V2.20

- Quality/Security/Unified verdes;
- Release/UI/Mobile verdes;
- Global Worker readiness verde separado;
- dedicated Core Certification workflow verde;
- synthetic stress verde;
- load/chaos/recovery verde;
- todas as dimensões do manifesto verificadas;
- zero execução real durante certificação;
- zero freeze implícito.
