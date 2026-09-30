# ADR-0066 — Business Team Access Sandbox Evidence

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0065 prepara o sandbox físico, mas um ambiente em execução não é evidência
suficiente para liberar o teste de lifecycle. Antes de criar conta de teste,
habilitar MFA, gravar uma revisão do registry ou testar revogação, o ambiente
precisa gerar uma linha de base auditável e sanitizada.

## Decisão

Adicionar uma camada de evidência read-only que observa:

- serviços Docker esperados em execução;
- issuer OIDC local do realm atlasquant-sandbox;
- tabelas registry_revisions e team_memberships;
- imagens pinadas de Keycloak e PostgreSQL;
- SHA-256 do compose, realm e schema do registry;
- timestamp UTC da coleta.

A evidência fica em diretório local ignorado pelo Git e não contém secrets,
tokens ou headers de autorização.

## Gate

O validador pode alcançar no máximo:

READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW

Esse estado apenas permite revisão administrativa do próximo teste manual em
sandbox. Ele não executa lifecycle.

## Lifecycle

Depois da linha de base, continuam exigidas evidências manuais separadas de:

1. conta individual;
2. username coerente com o convite;
3. enrollment de MFA forte;
4. challenge MFA bem-sucedido;
5. revisão persistida do registry;
6. read-back digest exato;
7. conta desabilitada;
8. sessões revogadas;
9. membership inativo;
10. read-back do membership inativo.

## Segurança

A camada:
- não chama Keycloak;
- não chama PostgreSQL;
- não invoca Docker no módulo Python;
- não cria conta;
- não habilita MFA;
- não grava registry;
- não revoga sessão;
- não autoriza produção.

O coletor PowerShell faz apenas leituras do sandbox local e grava um arquivo
local sanitizado.

## Compatibilidade

Complementa ADR-0048, ADR-0063, ADR-0064 e ADR-0065.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
