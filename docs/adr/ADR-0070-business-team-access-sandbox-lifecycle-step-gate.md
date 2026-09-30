# ADR-0070 — Business Team Access Sandbox Lifecycle Step Gate

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0068 e ADR-0069 separam autorização humana e ledger auditável. Ainda falta
uma fronteira por etapa para impedir que uma autorização de lifecycle seja
interpretada como permissão automática para executar todos os dez passos.

## Decisão

Adicionar um preflight read-only para exatamente o próximo step esperado.

O preflight exige:
- plano íntegro;
- autorização formal válida;
- ledger pronto para o próximo step;
- target igual ao next expected;
- baseline digest sem drift;
- saúde do sandbox verificada;
- OIDC verificado;
- schema do registry verificado;
- secrets mantidos localmente;
- ausência de targets de produção;
- caminho de cleanup pronto;
- solicitante igual ao administrador da autorização.

## Estado máximo antes do step

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION

O preflight gera um token específico para o step, mas não registra a decisão e
não executa o step.

## Pós-step

Um receipt produzido externamente é recalculado e comparado ao chain head do
ledger.

Estado máximo:

READY_FOR_MANUAL_LEDGER_APPEND_REVIEW

O review não faz append automático.

## Segurança

A camada não:
- cria conta;
- habilita MFA;
- grava registry;
- desabilita conta;
- revoga sessão;
- executa comando;
- faz append automático;
- autoriza produção/deploy/runtime.

## Compatibilidade

Complementa ADR-0067, ADR-0068 e ADR-0069.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
