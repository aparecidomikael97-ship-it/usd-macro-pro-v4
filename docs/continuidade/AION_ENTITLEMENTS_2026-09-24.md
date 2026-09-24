# AtlasQuant — AION Entitlements / Assinaturas — 2026-09-24

## Objetivo

Criar a camada persistente que separa quatro conceitos que não podem ser confundidos:

1. **Conta/login** — identidade e autenticação.
2. **Perfil** — USER, SALES ou ADMIN.
3. **Cobrança/promoção** — eventos financeiros ou benefícios comerciais.
4. **Entitlement** — evidência de que uma conta/cliente possui determinado direito de acesso.

A nova camada existe para impedir que pagamento, cupom ou simples aprovação local sejam tratados automaticamente como acesso real.

## Checkpoint Mestre v5

O Checkpoint Mestre passa a incluir:

`entitlements.records`

`entitlements.digest`

Checkpoints antigos são migrados em memória para a versão 5 sem declarar persistência até o salvamento explícito no runtime.

## Ciclo de vida

Estados possíveis:

- DRAFT
- APPROVED
- PROVIDER_READY
- ACTIVE_CONFIRMED
- SUSPENDED_CONFIRMED
- EXPIRED_CONFIRMED
- REVOKED_CONFIRMED

Estados terminados em `_CONFIRMED` exigem evidência externa concreta:

- `confirmed=true`;
- nome/fonte do provedor ou registro;
- ID externo;
- aprovação administrativa anterior.

Se um registro antigo ou manipulado declarar `ACTIVE_CONFIRMED` sem essas condições, a normalização rebaixa o estado para APPROVED ou DRAFT.

## Guardian

Nova feature flag:

`entitlement_activation=false`

Nova ação:

`activate_entitlement`

Risco:

`FINANCIAL`

Para um preflight ficar elegível são necessários simultaneamente:

- sessão ADMIN;
- solicitação aprovada;
- feature flag ligada;
- aprovação explícita daquela ação.

Mesmo assim:

`executes_entitlement=false`

Ou seja, o preflight nunca libera acesso sozinho.

## Separação de segurança

Uma solicitação de entitlement nunca altera automaticamente:

- `ATLASQUANT_USERS_JSON`;
- senha;
- papel USER/SALES/ADMIN;
- pagamento;
- cobrança;
- permissão de trading;
- execução real em corretora.

Esses efeitos permanecem explicitamente `false` no contrato.

## Interface AION

A aba **Assinaturas & Promoções** passa a conter também **Registro de Entitlements**.

O administrador pode:

- criar uma solicitação;
- identificar cliente/conta;
- definir um escopo técnico genérico, sem inventar preço/plano;
- registrar origem: MANUAL_GRANT, BILLING ou PROMOTION;
- registrar janela de início/expiração;
- aprovar a solicitação;
- verificar o preflight do Guardian.

A tela não oferece botão para inventar evidência de provedor nem marcar ACTIVE_CONFIRMED manualmente.

## Integração futura

Quando existir um registro de assinaturas/provedor realmente conectado, o fluxo poderá:

1. receber evento verificado;
2. associar o evento à solicitação aprovada;
3. registrar provider + external_id;
4. marcar lifecycle confirmado;
5. consultar se o entitlement está efetivo;
6. somente depois alimentar uma camada de provisionamento explicitamente aprovada.

Nenhuma dessas integrações externas é descrita como ativa hoje.

## Estado de verdade deste bloco

- contrato local/offline de entitlement: IMPLEMENTADO;
- Checkpoint Mestre v5: IMPLEMENTADO EM CÓDIGO;
- interface administrativa: IMPLEMENTADA EM CÓDIGO;
- ativação externa: DESLIGADA;
- provedor de assinatura: NÃO CONECTADO;
- pagamento: NÃO INTEGRADO;
- alteração automática de usuário/perfil: BLOQUEADA;
- trading real: BLOQUEADO.
