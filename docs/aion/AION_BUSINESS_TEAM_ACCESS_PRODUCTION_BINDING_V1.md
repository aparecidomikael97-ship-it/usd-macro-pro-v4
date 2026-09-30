# AION BUSINESS — Team Access Production Binding V1

## Objetivo

Preparar Equipe & Acessos para integração futura com identidade e sessões reais,
sem permitir que o AION provisione ou revogue acessos sozinho.

## Camada lógica reutilizada

O RBAC atual continua sendo a fonte de:
- perfis;
- permissões;
- tenant scope;
- strong-auth required;
- invitation plan;
- revocation plan;
- decisão do AION usando as mesmas permissões da interface.

## Evidência de conta

A conta real precisa:
- ser individual;
- corresponder ao username aprovado;
- não ser compartilhada;
- estar ativa;
- ser identificada por referência do provider.

Nenhuma senha ou secret entra neste contrato.

## MFA forte

Aceitos:
- PASSKEY;
- SECURITY_KEY;
- TOTP.

É necessário provar:
- enrollment;
- challenge verificado;
- factor_ref;
- timestamp.

## Registry persistido

O registry lógico é canonizado e recebe digest.

A evidência de persistência precisa:
- revision;
- digest anterior;
- storage_ref;
- persistência confirmada externamente;
- read-back confirmado;
- digest lido igual ao esperado.

A primeira revision aponta para genesis.

## Ativação

Somente quando convite, conta, MFA e registry casam exatamente o sistema chega a:

`READY_FOR_ADMIN_TEAM_ACCESS_ACTIVATION_REVIEW`

Isso não ativa acesso.

## Revogação

Uma revogação só é considerada externamente verificada quando:
- account disabled;
- all sessions revoked;
- membership inactive;
- registry read-back confirmado.

O módulo não executa nenhum desses passos.

## Autoridade

Sempre permanecem false:
- access_activation_authorized;
- session_activation_authorized;
- permission_escalation_authorized;
- billing_authorized;
- runtime_authorized.
