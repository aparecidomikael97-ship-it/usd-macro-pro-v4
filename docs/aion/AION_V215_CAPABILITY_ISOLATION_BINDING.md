# AION V2.15 — Signed Capability Isolation & Least Privilege

**Base:** V2.14 validated head `c2093b0ee3bae5719ca02c146c9994b1896136eb`

## Objetivo

Consolidar isolamento e capability security sem criar uma segunda matriz paralela de
permissões.

O V2.15 reaproveita:
- Capability Registry;
- Specialist Router e perfis de domínio;
- Tenant Isolation;
- Memory domain isolation;
- Role Authority;
- Tool Hub;
- V2.13 trust root e authority verification;
- V2.14 durable execution.

## Regra central

Um grant de autoridade V2.13 é necessário, mas **não é suficiente** para uma
capability concreta.

Cada capability operacional precisa de um segundo objeto assinado:

`ATLASQUANT_AION_CAPABILITY_SCOPE_GRANT_V1`

O scope grant é vinculado a:
- parent authority statement;
- authority_id;
- subject_id;
- tenant_id;
- workspace_id;
- domain;
- policy_id;
- capability_id;
- allowed_tools;
- allowed_actions;
- max_cost_usd;
- namespace;
- validity window;
- nonce;
- trust-root key id/version.

## Interseção de permissões

O grant nunca amplia o sistema. A capability efetiva é a **interseção** entre:

1. authority parent criptograficamente verificada;
2. capability list assinada no parent;
3. Capability Registry;
4. domínio oficial do Specialist Router;
5. role permitida pela capability;
6. tool ceiling da capability e do profile;
7. action ceiling do profile;
8. cost ceiling assinado;
9. tenant/workspace/domain namespace;
10. nonce/replay protection.

Se qualquer uma discordar, o resultado é BLOCKED.

## Isolamento de domínio

Os quatro domínios canônicos continuam:
- TRADER
- BUSINESS
- INVESTMENTS
- CORE

Uma authority pode até listar uma capability fora do domínio por erro, mas o V2.15
bloqueia o child grant se a capability não pertencer ao profile daquele domínio.

## Isolamento de tenant/workspace

O parent V2.13 já liga tenant/domain ao statement.

O V2.15 acrescenta `workspace_id` assinado e exige namespace canônico:

`tenant/<tenant>/workspace/<workspace>/domain/<DOMAIN>`

Isso vira o namespace de referência para recursos da execução: memória, tarefas,
artifacts e futuras credenciais scoped.

## Ferramentas

Uma ferramenta só pode aparecer no child grant se estiver:
- declarada em `Capability.allowed_tools`; e
- declarada no profile do domínio.

A ferramenta solicitada precisa estar explicitamente no child grant.

O gate não chama ferramenta.

## Ações

A action precisa pertencer ao profile do domínio e não pode estar em denied_actions.

Uma action solicitada precisa estar explicitamente no child grant.

## Role

O actor role precisa estar em `Capability.allowed_roles`.

Nenhum especialista pode ampliar role, tool, action ou scope além do parent/contexto.

## Orçamento

`max_cost_usd` faz parte do scope grant assinado.

A estimativa registrada da capability não pode ultrapassar esse teto. O Policy
Kernel posterior poderá impor um teto ainda menor; nunca maior.

## Relação com execução

Resultado positivo:
- `state=SCOPE_VERIFIED`
- `capability_scope_verified=True`

Mas continua:
- `execution_allowed=False`
- `approval_implied=False`
- `permissions_expanded=False`
- `tool_called=False`
- `executes_action=False`

V2.15 valida **escopo**, não executa.

## Critério de fechamento

- parent authority real obrigatória;
- tenant mismatch bloqueado;
- workspace mismatch bloqueado;
- namespace mismatch bloqueado;
- cross-domain capability bloqueada;
- capability não presente no parent bloqueada;
- role escalation bloqueada;
- tool escalation bloqueada;
- action escalation bloqueada;
- cost ceiling provado;
- tamper/signature invalid bloqueados;
- child window não ultrapassa parent;
- scope nonce replay bloqueado;
- parent replay bloqueado;
- nenhum flag/payload pode fabricar execution_allowed;
- gates canônicos verdes.
