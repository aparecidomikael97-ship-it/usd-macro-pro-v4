# ADR-0065 — Business Team Access Physical Sandbox

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0064 definiu o contrato E2E e a stack de referência. Antes de conectar
produção, é necessário um ambiente físico não produtivo, reproduzível e
isolado, com secrets fora do repositório e partida explicitamente humana.

## Decisão

Preparar um sandbox local baseado em Docker Compose com:

- Keycloak 26.7.5;
- PostgreSQL 18.6 para persistência do Keycloak;
- PostgreSQL 18.6 separado para o registry do AtlasQuant;
- realm atlasquant-sandbox importado sem usuários e sem client secret;
- portas expostas apenas em 127.0.0.1;
- PowerShell como launcher operacional para o ambiente Windows;
- PLAN ONLY como comportamento padrão;
- -Apply obrigatório para iniciar ou parar containers;
- confirmação adicional para remover volumes.

O start-dev do Keycloak existe exclusivamente no sandbox e não pode ser
promovido para produção.

## Secrets

O arquivo real sandbox.env.local:
- não é versionado;
- é explicitamente ignorado pelo Git;
- precisa substituir todos os placeholders;
- usa credenciais distintas;
- não é lido pela interface administrativa.

## Gate

O preflight read-only pode alcançar no máximo:

READY_FOR_ADMIN_TEAM_ACCESS_PHYSICAL_SANDBOX_START_REVIEW

Ele não executa Docker.

Depois do start manual, a verificação OIDC e o E2E da ADR-0064 continuam sendo
gates independentes.

## Segurança

Esta camada não autoriza:
- produção;
- deploy;
- runtime produtivo;
- criação automática de usuários;
- promoção de configuração de sandbox;
- gravação automática no registry;
- revogação automática;
- secrets no Git.

## Consequências

O projeto passa a ter infraestrutura reproduzível para validação física sem
confundir sandbox com produção.

## Compatibilidade

Complementa ADR-0048, ADR-0063 e ADR-0064.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
