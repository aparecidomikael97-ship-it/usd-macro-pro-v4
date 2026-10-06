# AION B2B — Future Executor Boundary V2

Status: **design-only / fail-closed / zero executor real**.

## Objetivo

Esta camada formaliza o limite entre a cadeia sintética já endurecida e qualquer
futuro desenho de executor.

Ela NÃO cria executor, provider binding, endpoint, payload, credencial, token,
network call, cobrança, contato com cliente, CRM write, provisionamento, deploy
ou mutação de produção.

## Base exigida

A boundary exige a cadeia V2 final endurecida:

- FinOps V2 local em 20.000 centavos;
- janela de environment V2 local em 180 segundos;
- RISKS e ENVIRONMENT_SCHEMA locais no V2;
- vocabulário completo de material perigoso no V2;
- V1 marcado LEGACY / NON-EXECUTABLE;
- Receipt V2 declarando legacy_v1_allowed=False;
- schemas Command/Adapter/Dry Run/Receipt V2 obrigatórios;
- Receipt exclusivamente sintético;
- authority/effect flags false;
- Adapter V2 exigindo contrato separado antes de qualquer executor.

## Estado máximo

`READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW`

Esse estado significa somente que a arquitetura pode discutir e especificar o
contrato futuro. O único próximo passo permitido é:

`DESIGN_EXECUTOR_CONTRACT_ONLY`

Não significa:

- executor criado;
- provider selecionado;
- credencial emitida;
- endpoint escolhido;
- comando executável gerado;
- billing autorizado;
- contato com cliente autorizado;
- CRM write autorizado;
- provisionamento autorizado;
- deploy autorizado;
- produção autorizada.

## Auditoria independente

O Red Team passou o HEAD de hardening final sem BLOCKER/HIGH/MEDIUM/LOW novos.
A execução independente da suíte pelo sandbox do Red Team continua marcada como
pendência procedural; o CI do repositório não substitui essa evidência externa.

A boundary registra essa condição como
`independent_dynamic_audit_pending=True`, sem transformá-la em autoridade.

## Regra para qualquer fase futura

Qualquer executor real exigirá, separadamente:

1. contrato de capacidade e readiness;
2. autenticação do receipt real;
3. idempotência persistente e replay protection apropriados;
4. rollback/compensação de produção por ação;
5. red-team próprio;
6. nova autorização explícita do Owner.

Nenhuma autorização histórica pode ser reutilizada como autorização nova.
