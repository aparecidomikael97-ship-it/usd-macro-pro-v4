# AION BUSINESS — Equipe & Acessos · Evidências do Sandbox V1

## Objetivo

Criar uma ponte auditável entre o sandbox físico e o teste E2E.

## Coleta automática permitida

Somente leitura:

- estado dos serviços Docker Compose;
- OIDC discovery do realm local;
- schema do PostgreSQL do registry;
- hashes SHA-256 dos arquivos de infraestrutura.

O coletor não registra senha, token ou secret.

## Arquivo local

O baseline é salvo em:

deploy/sandbox/team-access/.atlasquant_sandbox_evidence/team-access-baseline-evidence.json

O diretório é ignorado pelo Git.

## Validação

O CLI validate_team_access_sandbox_evidence.py valida o baseline de forma
fail-closed.

Estado máximo:

READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW

## Próxima fase

Conta, MFA, registry write e revogação continuam como testes manuais de sandbox.
A camada gera um template com os dez itens de evidência exigidos antes de
alimentar o runner E2E da ADR-0064.

## Produção

Nenhuma evidência deste sandbox autoriza promoção automática para produção.
