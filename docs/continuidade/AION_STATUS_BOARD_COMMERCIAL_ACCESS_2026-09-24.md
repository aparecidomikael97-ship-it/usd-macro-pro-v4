# AtlasQuant — Painel Mestre com Auditoria Comercial — 2026-09-24

## Objetivo

Levar a auditoria Conta × Entitlement para o Painel Mestre do AION sem transformar diagnóstico em enforcement.

A mesma auditoria é calculada uma única vez por execução do AION ADMIN e alimenta:

- Assinaturas & Promoções;
- Painel Mestre de Estado;
- retorno resumido do console administrativo.

## Regra de confirmação

O item **Auditoria comercial Conta × Entitlement** só pode ficar `CONFIRMED` quando:

1. a auditoria foi realmente calculada;
2. o Checkpoint Mestre runtime está `CONFIRMED`;
3. não existem alterações locais pendentes;
4. existe pelo menos uma conta USER ativa para validar;
5. não há USER sem APP_ACCESS efetivo;
6. não há duplicidade de entitlement efetivo;
7. não há entitlement APP_ACCESS efetivo órfão.

Se qualquer uma dessas condições falhar, o Painel Mestre usa `BLOCKED` ou `UNKNOWN`.

## Importante

Mesmo quando o item fica `CONFIRMED`, isso significa apenas:

**a população USER configurada foi reconciliada sem divergência com os entitlements APP_ACCESS presentes na evidência atual.**

Isso NÃO prova:

- pagamento;
- assinatura cobrada;
- venda;
- integração de provedor;
- enforcement de login;
- provisionamento automático;
- revogação automática.

## Estados relevantes

### CONFIRMED

Runtime confirmado, checkpoint limpo, USER ativo existente e auditoria sem divergências.

### BLOCKED

Exemplos:

- checkpoint com alterações locais não persistidas;
- USER sem entitlement efetivo;
- duplicidade;
- entitlement órfão.

### UNKNOWN

Exemplos:

- auditoria não fornecida;
- runtime do Checkpoint não confirmado;
- nenhuma população USER ativa para validar.

## Segurança

Nenhuma mudança neste bloco:

- altera login;
- altera role;
- cria conta;
- revoga conta;
- chama pagamento;
- concede entitlement;
- habilita corretora;
- habilita trading real.

O enforcement comercial continua explicitamente desligado.
