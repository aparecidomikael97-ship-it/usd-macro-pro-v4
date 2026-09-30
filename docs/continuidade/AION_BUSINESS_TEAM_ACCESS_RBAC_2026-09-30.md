# Continuidade — AION BUSINESS Team Access / RBAC V1

Data: 2026-09-30

## Ponto de partida

Empilhado sobre a Draft PR #435, que consolidou o Checkpoint Mestre de 30/09.

## Bloco

Implementada a primeira camada de Equipe & Acessos:

- reaproveita autenticação AtlasQuant existente;
- membership individual por username;
- 7 perfis Business;
- escopo explícito por tenant;
- strong-auth obrigatório;
- AION usa a mesma decisão de acesso;
- cross-tenant bloqueado;
- ações críticas fora do RBAC Business;
- convite e revogação apenas como planos administrativos;
- 23ª visão no Painel Business;
- ADR-0048;
- testes e CI.

## Estado

IMPLEMENTADO / EM VALIDAÇÃO.

Ainda pendente para produção:
- provisionamento real de convite/conta;
- MFA/2FA real;
- persistência real do registry;
- revogação física de sessão/conta;
- UI completa de gestão da equipe.

Nenhuma conta foi criada e nenhuma permissão real foi aplicada por este bloco.
