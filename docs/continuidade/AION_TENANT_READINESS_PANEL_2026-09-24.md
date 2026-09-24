# AtlasQuant — Painel de prontidão do AION pessoal — 2026-09-24

## Objetivo

Corrigir a diferença entre a fundação de isolamento do AION por assinante e a interface administrativa.

O contrato de tenant já existe em código, mas o administrador precisava de uma visão explícita de prontidão.

Este bloco adiciona somente diagnóstico/readiness.

## Onde aparece

Na área:

**Assinaturas & Promoções → AION pessoal · isolamento por assinante**

O ADMIN visualiza:

- quantidade de entitlements `AION_PERSONAL`;
- quantos estão efetivos e confirmados;
- quantas referências de assinante têm direito efetivo;
- duplicidades de entitlement efetivo;
- estado de isolamento cross-tenant;
- regras de memória e privacidade;
- estado de provedor, billing e trading.

## Regras de verdade

O painel não chama um entitlement de efetivo apenas por existir.

Ele usa o mesmo contrato de `entitlement_effective`, portanto exige estado `ACTIVE_CONFIRMED`, evidência de provedor e janela temporal válida.

`APP_ACCESS` não é tratado como `AION_PERSONAL`.

Um assinante só entra na contagem de elegíveis quando existe entitlement efetivo do escopo exato `AION_PERSONAL`.

## Segurança

O painel declara explicitamente:

- Meu AION ainda NÃO está ativado para assinantes nesta tela;
- subscriber shell: DESLIGADO;
- persistência runtime pessoal: NÃO CONFIRMADA;
- provisionamento automático: NÃO;
- memória ADMIN herdada: NÃO;
- documentos privados do projeto herdados: NÃO;
- cross-tenant: BLOQUEADO;
- provedor externo automático: DESLIGADO;
- cobrança automática: DESLIGADA;
- trading real: BLOQUEADO.

## O que este bloco NÃO faz

- não cria tenant;
- não gera sessão do assinante;
- não grava memória pessoal;
- não chama o contrato de tenant store;
- não ativa provedor de IA;
- não cobra;
- não altera login;
- não cria/revoga conta;
- não concede entitlement;
- não habilita trading real.

## Relação com a persistência futura

O PR de persistência isolada do Meu AION é um trabalho separado.

Este painel não assume que essa persistência está pronta em produção. Mesmo que o contrato de store exista em código, a interface continua mostrando:

**Persistência pessoal em produção: NÃO CONFIRMADA**

até existir evidência real de runtime/deploy.

## Regra de duplicidade

Se o mesmo `subject_ref` possuir mais de um entitlement `AION_PERSONAL` efetivo, o ADMIN recebe alerta para revisão.

A duplicidade nunca cria múltiplos tenants automaticamente.

## Estado deste bloco

- resumo local de prontidão: IMPLEMENTADO EM CÓDIGO;
- painel ADMIN: IMPLEMENTADO EM CÓDIGO;
- testes dedicados: INCLUÍDOS NO QUALITY GATE;
- tenant shell para cliente: DESLIGADO;
- persistência pessoal em produção: NÃO CONFIRMADA;
- IA externa automática: DESLIGADA;
- cobrança automática: DESLIGADA;
- trading real: BLOQUEADO.
