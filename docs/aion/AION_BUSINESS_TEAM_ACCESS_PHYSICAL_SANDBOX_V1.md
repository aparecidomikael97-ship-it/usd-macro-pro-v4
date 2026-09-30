# AION BUSINESS — Equipe & Acessos · Sandbox Físico V1

## Entrega

A camada física do sandbox prepara um ambiente local e isolado para executar,
posteriormente, o E2E definido na ADR-0064.

### Componentes

- Keycloak 26.7.5;
- PostgreSQL 18.6 dedicado ao Keycloak;
- PostgreSQL 18.6 dedicado ao registry;
- OIDC realm atlasquant-sandbox;
- public client com PKCE S256;
- portas somente em 127.0.0.1;
- scripts PowerShell de start, verificação e stop;
- preflight Python read-only;
- secrets locais ignorados pelo Git.

## Fluxo administrativo

1. copiar sandbox.env.example para sandbox.env.local;
2. substituir placeholders por valores longos e distintos;
3. executar Start-TeamAccessSandbox.ps1 sem -Apply;
4. revisar o plano;
5. somente com decisão explícita local, executar com -Apply;
6. verificar OIDC;
7. executar o lifecycle E2E de conta, MFA, registry e revogação;
8. submeter a evidência ao gate administrativo.

## Estado máximo automático

READY_FOR_ADMIN_TEAM_ACCESS_PHYSICAL_SANDBOX_START_REVIEW

Esse estado não inicia containers.

## Produção

O bundle usa start-dev e é proibido para produção. Produção terá arquitetura,
TLS, storage, secrets, observabilidade e aprovação próprios.
