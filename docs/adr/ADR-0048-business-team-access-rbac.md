# ADR-0048 — Equipe Business usa identidade individual, RBAC e escopo explícito por tenant

Título: Equipe Business usa identidade individual, RBAC e escopo explícito por tenant  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O Business precisa permitir que funcionários ajudem Mikael sem compartilhar o
login administrativo e sem obter acesso a clientes ou funções fora da sua
responsabilidade.

## Problema

Compartilhar credencial administrativa elimina responsabilização individual,
aumenta risco de vazamento e permite que uma ação do AION ignore a separação por
cliente.

## Alternativas consideradas

1. Compartilhar o login ADMIN.
2. Criar um segundo sistema de autenticação só para Business.
3. Reutilizar o login AtlasQuant existente e adicionar uma camada Business de
   membership, perfil, tenant scope e strong-auth.

## Decisão

Adotar a alternativa 3.

Perfis Business:
- BUSINESS_OWNER;
- BUSINESS_MANAGER;
- FINANCE;
- SUPPORT;
- MARKETING;
- OPERATOR;
- VIEWER.

Cada membership é individual, vinculado ao username autenticado e a uma lista
explícita de tenants. O AION deve obedecer à mesma decisão de permissão usada
pela interface.

## Consequências

Funcionários podem receber somente o acesso necessário. Cross-tenant, escalada
automática e compartilhamento do login administrativo permanecem proibidos.

## Componentes afetados

- login/access-control;
- Business Admin;
- AION Business;
- tenant isolation;
- audit trail;
- onboarding/offboarding.

## Segurança

Ações críticas como deploy, billing, secrets, runtime, expansão, publicação e
trading real não são concedidas por perfil de equipe e continuam em gates
separados. Strong-auth é requerido pela camada Business.

## Compatibilidade

A autenticação base USER/SALES/ADMIN continua sendo a fonte de identidade.
RBAC Business é uma camada adicional e não substitui o controle de acesso
existente.

## Rollback/migração

O módulo é fail-closed e administrativo. Desativar a camada remove permissões
Business adicionais sem criar fallback para ADMIN.

## PR/commit relacionado

Draft PR de Equipe & Acessos / RBAC V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
