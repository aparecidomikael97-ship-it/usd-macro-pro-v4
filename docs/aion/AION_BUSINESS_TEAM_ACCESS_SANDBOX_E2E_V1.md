# AION BUSINESS — Equipe & Acessos · Sandbox E2E V1

## Objetivo

Validar ponta a ponta, em ambiente não produtivo, o contrato de Equipe &
Acessos definido pelo RBAC e pelo production binding sem conceder ao AION
autoridade para executar mutações externas.

## Stack de referência escolhida para o sandbox

| Camada | Escolha | Estado |
| --- | --- | --- |
| Identity provider | Keycloak | Selecionado para sandbox |
| Protocolo | OIDC | Selecionado para sandbox |
| MFA forte | Passkey/WebAuthn, security key, TOTP | Obrigatório |
| Registry | PostgreSQL | Selecionado para sandbox |
| Revogação | Keycloak Admin REST via adapter | Selecionado para sandbox |

A escolha acima é uma referência controlada de validação. Produção continua sem
binding físico e sem autorização automática.

## Pipeline E2E

O módulo atlasquant_aion_business_team_access_sandbox_e2e.py valida:

1. provider Keycloak em ambiente SANDBOX;
2. suporte a conta individual e autenticação forte;
3. conta provisionada externamente e atestada;
4. challenge de MFA validado;
5. PostgreSQL declarado como storage do registry;
6. registry versionado persistido externamente;
7. read-back com digest canônico exato;
8. revisão de ativação da camada anterior;
9. adapter de revogação do Keycloak;
10. desabilitação de conta, revogação de sessão e membership inativo atestados;
11. revisão administrativa de saída do sandbox.

## Estado máximo

READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_EXIT_REVIEW

Esse estado significa somente que a evidência entregue passou no contrato.
Não significa que produção está autorizada.

## Proteções

- fail-closed;
- ambiente de produção bloqueado;
- secret material bloqueado;
- side effects externos declarados bloqueiam o binding;
- provider/storage/connector divergentes bloqueiam;
- revogação parcial bloqueia;
- nenhuma chamada de rede no módulo;
- nenhuma execução de processo;
- nenhum writer físico;
- nenhuma mudança de permissão.

## Próximo gate

Depois de CI verde desta camada, o próximo trabalho técnico é montar o ambiente
sandbox físico isolado e conectar adapters reais com secrets fora do
repositório, mantendo aprovação administrativa separada para qualquer ação
externa.
