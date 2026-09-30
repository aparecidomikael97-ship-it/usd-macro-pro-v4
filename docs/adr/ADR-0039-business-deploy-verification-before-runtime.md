# ADR-0039 — Deploy verificado precede qualquer decisão de runtime do AION Business

- Título: Deploy verificado precede qualquer decisão de runtime do AION Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0038 separa consolidação técnica, deploy e runtime. Faltava definir a
evidência necessária entre um futuro deploy e uma futura ativação de runtime.

## Problema

Sem verificação pós-deploy, um artefato poderia ser considerado pronto para
runtime apenas porque o deploy terminou, mesmo com SHA incorreto, falha de UI,
observabilidade ruim ou ausência de rollback.

## Decisão

Criar quatro contratos:

1. registro explícito de autorização deploy-only;
2. preflight read-only;
3. verificação pós-deploy;
4. packet separado de decisão de runtime.

O deploy precisa manter BUSINESS runtime OFF e passar SHA, ambiente, health,
UI/mobile, observabilidade e rollback.

O token de deploy é `AUTHORIZE_BUSINESS_DEPLOY_ONLY`.

A próxima fronteira usa `AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION`, mas esse token
não é consumido por este módulo.

## Consequências

Deploy passa a ser um evento verificável e independente de runtime.

## Segurança

Nenhuma função deste ADR executa deploy ou ativa runtime.

## Compatibilidade

ADR-0038 prepara o handoff. Este ADR verifica o deploy e abre somente a fronteira
administrativa seguinte.

## Rollback

Read-only/administrativo; sem efeitos externos a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
