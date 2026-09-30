# AION BUSINESS — Equipe & Acessos · Plano de Lifecycle Sandbox V1

## Objetivo

Transformar o baseline validado em um plano manual de teste, sem automatizar
nenhuma mutação.

## Pré-condições

- baseline do sandbox validado;
- digest do baseline presente;
- username de teste iniciado por sandbox.;
- tenant explícito;
- fator PASSKEY, SECURITY_KEY ou TOTP;
- administrador solicitante identificado.

## Plano

O plano contém dez passos do ciclo completo: criação de conta, MFA, persistência
e read-back do registry, disable, revogação e validação final.

Cada passo informa:
- ordem;
- se é mutação;
- evidência obrigatória;
- necessidade de aplicação manual.

## Fronteira

O plano não é uma autorização.

Estado máximo:
READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION

Mensagens genéricas como “vamos lá” não equivalem ao token formal definido na
ADR-0067 para uma execução futura do lifecycle.
