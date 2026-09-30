# AION BUSINESS Team Access / RBAC V1

## Objetivo

Permitir equipe com contas individuais e menor privilégio, mantendo Mikael como
autoridade administrativa.

## Perfis

- BUSINESS_OWNER
- BUSINESS_MANAGER
- FINANCE
- SUPPORT
- MARKETING
- OPERATOR
- VIEWER

## Regras

- uma conta por pessoa;
- login ADMIN não é compartilhado;
- cada pessoa recebe tenants/clientes explícitos;
- strong-auth é obrigatório na camada Business;
- perfil não pode elevar a si próprio;
- cross-tenant é bloqueado;
- o AION obedece à mesma decisão de permissão da interface;
- ações críticas continuam em gates separados.

## Convite

`prepare_team_invitation_plan` apenas prepara uma revisão administrativa. Não
cria conta, não envia e-mail e não aplica membership.

## Registro

`audit_team_registry` rejeita usuários duplicados, membership inválido e
tenant fora do conjunto conhecido.

## Decisão de ação

`team_access_decision` valida:
- sessão autenticada;
- integridade do membership;
- username da sessão igual ao membership;
- membership ativo;
- strong-auth;
- tenant em escopo;
- ação conhecida;
- permissão do perfil.

O resultado contém `aion_must_obey_same_decision=true`.

## Revogação

`prepare_membership_revocation_plan` gera apenas um plano de offboarding. A
revogação física da conta/sessão fica em camada separada e auditável.
