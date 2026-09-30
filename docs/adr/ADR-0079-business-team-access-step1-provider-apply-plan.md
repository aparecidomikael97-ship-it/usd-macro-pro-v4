# ADR-0079 — Business Team Access Step 1 Provider Apply Plan

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0078 produz um execution envelope curto e revalidado para o Step 1, mas
deliberadamente não gera comando de provider.

Antes de qualquer runner físico, o contrato da mutação precisa ser congelado em
um artefato sem segredo e sem material executável.

## Decisão

Criar um Step 1 Provider Apply Plan read-only.

O plano é gerado somente quando o execution envelope passa seu verificador de
integridade.

A operação congelada é:

- provider: KEYCLOAK;
- realm: atlasquant-sandbox;
- method: POST;
- relative path: /admin/realms/atlasquant-sandbox/users;
- content type: application/json;
- expected status: 201;
- 400/403/409/500: hard stop.

O body contém somente:

- username sandbox;
- enabled=true;
- emailVerified=false;
- requiredActions vazio;
- atributos não secretos de sandbox/session/tenant/step.

O body não contém credentials nem password.

## Endpoint

A operação segue o Keycloak Admin REST API para criação de usuário em
POST /admin/realms/{realm}/users.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_REVIEW

## Segurança

O plano nunca contém:

- Authorization header;
- access token;
- password;
- credentials;
- comando PowerShell;
- comando cURL.

Também não:

- chama Keycloak;
- cria conta;
- produz execution receipt;
- autoriza ledger append;
- habilita executor;
- autoriza produção/deploy/runtime.

## Integridade

apply_plan_digest cobre:

- execution envelope digest;
- plan digest;
- operator session;
- baseline digest;
- Step 1;
- username;
- tenant scope;
- factor;
- provider operation completa.

Qualquer alteração em endpoint, payload ou metadados quebra o binding.

## Compatibilidade

Complementa ADR-0078.
