# AtlasQuant — Auditoria Conta × Entitlement — 2026-09-24

## Objetivo

Adicionar uma reconciliação administrativa de leitura entre:

- contas configuradas no AtlasQuant;
- perfil da conta;
- estado ativo/inativo da conta;
- entitlements `APP_ACCESS` confirmados.

Esta auditoria existe para encontrar inconsistências **antes** de qualquer política futura de enforcement.

## O que ela NÃO faz

A auditoria não:

- participa da autenticação;
- libera acesso;
- bloqueia login;
- revoga conta;
- cria conta;
- altera USER/SALES/ADMIN;
- chama provedor de pagamento;
- concede promoção;
- altera trading;
- executa ordens reais.

Todos esses efeitos permanecem explicitamente desligados.

## Regra por perfil

### USER

Conta USER ativa é comparada com entitlement efetivo `APP_ACCESS`.

Estados de auditoria:

- `ENTITLEMENT_EFFECTIVE`
- `NO_EFFECTIVE_ENTITLEMENT`
- `DUPLICATE_EFFECTIVE_ENTITLEMENTS`

### ADMIN / SALES

São tratados como perfis internos:

`INTERNAL_ROLE_EXEMPT`

A auditoria não exige entitlement comercial para esses perfis.

### Conta inativa

Estado:

`ACCOUNT_INACTIVE`

Conta inativa não entra na contagem de USER comercial ativo esperado.

## Entitlement órfão

Quando existe entitlement efetivo `APP_ACCESS` cuja referência não corresponde a uma conta configurada:

`ORPHAN_EFFECTIVE_ENTITLEMENT`

Isso é sinal de revisão, não autorização para criar uma conta automaticamente.

## Interface AION

A área **Assinaturas & Promoções → Registro de Entitlements** passa a exibir:

- USER ativos;
- USER com direito efetivo;
- USER sem direito efetivo;
- entitlements órfãos;
- estado de cada conta;
- duplicidades.

O painel mostra explicitamente:

- Enforcement: DESLIGADO
- autenticação alterada: NÃO
- provisionamento automático: NÃO
- revogação automática: NÃO

## Estado de verdade

- auditoria local/offline: IMPLEMENTADA;
- integração no AION ADMIN: IMPLEMENTADA EM CÓDIGO;
- enforcement comercial no login: DESLIGADO;
- provisionamento automático: DESLIGADO;
- revogação automática: DESLIGADA;
- pagamento conectado: NÃO CONFIRMADO;
- produção Render com bundle novo: ainda depende da reconciliação já registrada para quando o administrador estiver no computador.
