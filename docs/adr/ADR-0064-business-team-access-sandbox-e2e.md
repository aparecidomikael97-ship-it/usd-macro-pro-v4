# ADR-0064 — Business Team Access Sandbox E2E

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0063 definiu que produção só pode avançar com evidência externa de conta
individual, autenticação forte, registry persistido com read-back e revogação
comprovável. O passo seguinte é provar o ciclo completo em ambiente não
produtivo antes de qualquer integração real.

## Decisão

Adotar como stack de referência para validação de sandbox:

- Identity provider: **Keycloak**;
- protocolo de identidade: **OpenID Connect (OIDC)**;
- autenticação forte alvo: **Passkey/WebAuthn, security key ou TOTP**;
- storage do registry: **PostgreSQL**;
- connector de revogação: **Keycloak Admin REST**, limitado por adapter;
- execução: somente por evidência fornecida ao contrato; este módulo não faz
  chamadas externas.

A seleção é SANDBOX_VALIDATION_ONLY. Ela não conclui a escolha operacional de
produção, não configura secrets e não autoriza deploy/runtime.

## Racional

Keycloak atende o desenho de independência porque pode ser operado sob controle
do próprio ecossistema, expõe OIDC e suporta WebAuthn/passkeys e OTP. A camada
administrativa permite validar a capacidade de revogação sem conceder ao AION
autoridade direta.

PostgreSQL é usado como referência para o registry por oferecer persistência
transacional adequada a snapshots versionados e read-back verificável.

## Contrato E2E

O fluxo de sandbox só fica pronto quando todos os gates passam:

1. binding do identity provider;
2. conta individual atestada;
3. MFA forte atestado;
4. binding do PostgreSQL;
5. persistência do registry atestada e read-back digest exato;
6. revisão de ativação da ADR-0063 pronta;
7. binding do connector de revogação;
8. conta desabilitada, sessões revogadas, membership inativo e read-back
   comprovados por evidência do sandbox.

O máximo automático é READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_EXIT_REVIEW.

## Fail-closed

Bloqueiam o sandbox:

- ambiente marcado como produção;
- secret/credential material entregue ao contrato;
- provider/storage/connector diferente do stack de referência;
- evidência de side effect externo já executado pelo chamador;
- ausência de conta individual;
- MFA sem challenge validado;
- read-back divergente;
- revogação parcial.

## Segurança

A camada não:

- cria conta;
- envia convite;
- recebe ou grava senha/token;
- habilita MFA;
- grava PostgreSQL;
- chama Keycloak;
- revoga sessão;
- desabilita conta;
- eleva perfil;
- expande tenant scope;
- cobra;
- deploya;
- ativa runtime.

## Consequências

O projeto ganha um contrato executável para o lifecycle completo antes de
conectar infraestrutura real. A próxima etapa física continua sendo provisionar
um ambiente sandbox isolado e fornecer evidência real ao mesmo contrato.

## Compatibilidade

Complementa ADR-0048 e ADR-0063.

## Rollback

Read-only no runtime. Remover o módulo não altera identidades, sessões ou
registry externos.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
