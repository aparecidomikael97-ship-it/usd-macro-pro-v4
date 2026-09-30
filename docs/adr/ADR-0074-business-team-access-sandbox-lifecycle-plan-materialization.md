# ADR-0074 — Business Team Access Sandbox Lifecycle Plan Materialization

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

Após um baseline real validado e explicitamente aceito, ainda é necessário
materializar o plano concreto do lifecycle com username de teste, tenant scope e
fator MFA. Essa materialização não pode ser confundida com autorização para
executar o plano.

## Decisão

Criar uma camada que:

1. relê e revalida o baseline bruto;
2. exige baseline acceptance verificado;
3. chama o builder endurecido do lifecycle;
4. gera um materialization digest;
5. produz um pacote de plano para revisão administrativa.

## Inputs

- baseline evidence bruto;
- baseline acceptance verificado;
- test username sandbox-scoped;
- tenant ids;
- factor type: PASSKEY, SECURITY_KEY ou TOTP;
- requested_by.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW

## Fronteira

O pacote:
- contém as 10 etapas do plano;
- mantém plan digest;
- mantém baseline digest;
- mantém acceptance record digest;
- mantém operator session id;
- não cria lifecycle authorization record;
- não executa step;
- não autoriza produção/deploy/runtime.

A autorização formal do lifecycle continua em ADR-0068.

## Compatibilidade

Complementa ADR-0067, ADR-0068 e ADR-0073.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
