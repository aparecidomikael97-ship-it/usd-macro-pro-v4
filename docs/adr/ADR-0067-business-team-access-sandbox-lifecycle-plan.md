# ADR-0067 — Business Team Access Sandbox Lifecycle Plan

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0066 permite validar o baseline físico do sandbox. ADR-0073 acrescenta a
exigência de aceitação humana explícita do baseline antes da construção do
plano. O passo seguinte envolve
mutações intencionais, ainda que somente no sandbox: criar conta de teste,
enrolar MFA, gravar uma revisão do registry, desabilitar a conta e revogar
sessões. Essas ações não devem nascer de uma mensagem genérica nem ser
automatizadas pelo AION.

## Decisão

Criar um plano de lifecycle de dez etapas, sem executor, vinculado ao digest do
baseline validado.

O teste exige username iniciado por sandbox., tenant explícito e um fator forte
entre PASSKEY, SECURITY_KEY ou TOTP.

## Etapas

1. criar conta individual sandbox;
2. enrolar autenticação forte;
3. validar challenge;
4. gravar revisão do registry;
5. verificar read-back exato;
6. desabilitar conta sandbox;
7. revogar sessões sandbox;
8. marcar membership inativo;
9. verificar read-back inativo;
10. montar pacote final E2E.

## Decisão explícita

Antes de qualquer execução manual futura, o plano exige o token:

AUTHORIZE_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST

e os acknowledgements:

- SANDBOX_ONLY;
- NO_PRODUCTION_TARGETS;
- TEST_IDENTITY_ONLY;
- SECRETS_STAY_LOCAL;
- MANUAL_STEP_BY_STEP_APPLY;
- STOP_ON_FIRST_MISMATCH;
- REVOCATION_AND_CLEANUP_REQUIRED.

A existência do token no contrato não registra autorização.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION

## Segurança

A camada não:
- cria conta;
- habilita MFA;
- grava registry;
- desabilita conta;
- revoga sessão;
- registra decisão;
- executa comando;
- autoriza produção/deploy/runtime.

## Compatibilidade

Complementa ADR-0048 e ADR-0063 até ADR-0066.

## Supersedes

Nenhum.

## Superseded by

Nenhum.


## Entrada endurecida por ADR-0073

O builder do lifecycle exige baseline acceptance binding válido. Baseline
técnico isolado não é mais suficiente para produzir um plano.
