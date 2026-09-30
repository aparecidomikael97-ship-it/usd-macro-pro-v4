# AION BUSINESS Master Readiness Panel V1

Schema: `ATLASQUANT_AION_BUSINESS_MASTER_READINESS_V1`

## Objetivo

Dar uma leitura única e simples do estado do AION Business, separando três
camadas que não podem ser confundidas:

1. DEMO
2. PILOT
3. LIVE

## DEMO

A camada DEMO consolida:

- certificação Business;
- Demo UI;
- treinamento;
- diagnóstico/proposta;
- Portal do Cliente;
- onboarding;
- Customer Success/SLA;
- finanças/capacidade;
- tendências/melhoria contínua;
- captação/comercial;
- Hub de Integrações;
- privacidade/auditoria.

Completar DEMO não autoriza piloto nem runtime.

## PILOT

Para entrar em revisão de piloto, são necessários gates separados:

- treinamento administrativo concluído;
- pacote/escopo revisado;
- privacidade revisada;
- SLA revisado;
- economia/margem revisada;
- capacidade revisada;
- escopos de integração revisados;
- rollback revisado;
- contrato/template revisado;
- operador humano definido.

Mesmo com 100%, o estado é somente `PILOT_REVIEW_REQUIRED`.

## LIVE

Runtime real exige gates próprios:

- piloto autorizado;
- aprovação formal de runtime;
- credenciais reais provisionadas com segurança;
- saúde dos provedores validada;
- rollback de produção verificado;
- ações externas aprovadas.

Completar esses campos ainda produz `LIVE_REVIEW_REQUIRED`; o módulo nunca
ativa runtime.

## Segurança

O painel é agregador/read-only.

Ele não:

- autoriza piloto;
- ativa runtime;
- envia contato;
- assina contrato;
- cobra;
- publica;
- faz deploy.
