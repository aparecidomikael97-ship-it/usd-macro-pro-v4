# AION V2.18 — Constitution / Policy Kernel

**Base:** V2.17 head `b68c2319407690bbc2678974089f1087d9aac3b5`

## Objetivo

Consolidar as regras invioláveis do AION em código versionado e determinístico,
fora de prompts e fora da interpretação do modelo.

O Policy Kernel decide somente se uma intenção pode prosseguir para gates
posteriores. Ele nunca executa a intenção.

## Constituição canônica

A função `constitution_manifest()` retorna a única constituição aceita pelo
V2.18, com:
- schema;
- policy id;
- version;
- invariants;
- action rules;
- critical actions;
- policy source;
- digest canônico.

`assert_constitution_integrity` rejeita qualquer manifesto diferente, mesmo que o
caller recalcule um hash próprio.

## Invariantes

Entre os invariantes canônicos:

- LLM não é autoridade;
- memória não concede permissão;
- health não implica approval;
- readiness não implica execution;
- approval não implica execution;
- capability scope não amplia parent;
- agente não pode se autoaprovar;
- agente não pode mudar política;
- merge/deploy/payment/trading/secret/tenant-delete nunca são automáticos;
- kill switch não é mutado automaticamente;
- cross-tenant não é implícito;
- Policy Kernel nunca retorna `execution_allowed=True`.

## Ações canônicas

O kernel possui regras explícitas para:

- DIAGNOSTIC_READ
- DRAFT
- INTERNAL_WRITE
- EXTERNAL_SIDE_EFFECT
- SEND_EXTERNAL_MESSAGE
- CRM_MUTATION
- PAYMENT
- REAL_TRADING
- MERGE_MAIN
- DEPLOY_PRODUCTION
- WRITE_SECRET
- TENANT_DELETE
- CHANGE_POLICY

Ação não listada é BLOCKED.

## Evidências exigidas

O kernel compõe:

1. V2.13 authority verification;
2. V2.15 signed capability scope;
3. V2.16 operational resilience;
4. V2.17 multi-agent governance;
5. V2.14 durable execution quando a ação exige mutação;
6. owner approval para ações críticas;
7. budget restante e ceiling assinado;
8. privacy review quando aplicável;
9. real-trading flag separado para REAL_TRADING;
10. Global Kill Switch.

Nenhuma evidência isolada promove a intenção.

## Owner approval

Approval para ação crítica deve estar ligado a:
- action;
- tenant;
- domain;
- HUMAN_OWNER;
- current policy digest;
- exact approved=True.

Approval errado, de outro tenant/domínio ou de outra versão da política é
considerado ausente.

Mesmo quando presente:
- approval não executa;
- policy não executa;
- execution gate posterior ainda é obrigatório.

## Kill Switch

Global Kill Switch bloqueia ações sensíveis independentemente das demais evidências.

DIAGNOSTIC_READ continua permitido em postura `STOPPED_BY_KILL_SWITCH` para
permitir diagnóstico seguro.

O kernel nunca altera o kill switch.

## Degraded mode

Ações críticas exigem `NORMAL_MONITORED`.

DRAFT e DIAGNOSTIC_READ possuem regras mais permissivas de read-only/degraded para
permitir investigação sem efeitos externos.

## Custos

A intenção não pode ultrapassar:
- `max_cost_usd` do capability scope assinado;
- budget restante recebido do host.

Nenhum fallback pago é habilitado automaticamente.

## Trading real

REAL_TRADING exige simultaneamente:
- authority;
- capability scope;
- normal operational posture;
- durable EXTERNAL_EFFECT preparado;
- owner approval ligado ao policy digest;
- budget válido;
- `real_trading_enabled=True`.

Mesmo com tudo isso:
- `automatic_real_trading=False`;
- `execution_allowed=False`.

## Tenant deletion / LGPD

TENANT_DELETE exige:
- owner approval;
- durable execution preparada;
- privacy review verificada;
- tenant/domain bindings válidos.

O V2.18 não apaga dados.

## Mudança de política

`propose_constitution_change` é review-only:
- não muta a constituição ativa;
- não aplica proposta;
- não muda version;
- não concede execução.

Qualquer mudança real exige ADR posterior, revisão e nova certificação.

## Critério de fechamento

- manifest determinístico;
- tamper de invariants/rules bloqueado;
- unknown action bloqueada;
- approval misbound bloqueado;
- kill switch dominante;
- degraded mode bloqueia sensíveis;
- authority/capability/tenant/domain obrigatórios;
- durable mode obrigatório conforme ação;
- budget e signed ceiling;
- privacy review;
- real trading flag separado;
- policy change review-only;
- policy progress nunca igual a execution.

## Coordinator hardening

Para ações que exigem owner approval, o binding action/tenant/domain/policy não é mais
suficiente sozinho. O host precisa fornecer também evidência explícita de que a
aprovação foi verificada fora do LLM/agente.

Assim:
- approval mapping válido + evidence não verificada => BLOCKED;
- evidence upstream com tipo inválido => BLOCKED;
- authority/capability/resilience que aleguem execução em desacordo com seus contratos => BLOCKED;
- Policy Kernel continua sem conceder execution authority.

