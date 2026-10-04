# ADR-0018 — AION Core é provider-neutral e exige fallback local/offline

- Título: AION Core é provider-neutral e exige fallback local/offline
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION precisa operar em Trader, Negócios, Investimentos e Core por muitos anos.
Modelos e fornecedores mudam, preços mudam, quotas falham e providers podem ficar
indisponíveis.

O repositório já possui um adapter OpenAI funcional e contratos locais, mas o Core
não pode ficar arquiteturalmente preso a esse adapter.

## Problema

Acoplar orchestration, policy ou memória a um provider específico causaria:
- lock-in;
- falha ampla em outage do provider;
- dificuldade de modo offline/local;
- migrações estruturais para trocar modelo;
- dependência de pricing/configuração externa.

## Alternativas consideradas

Foram rejeitados:
- OpenAI como tipo estrutural do Core;
- um único provider configurável por vez sem fallback;
- fallback externo automático pago;
- considerar provider HEALTHY sem request/heartbeat evidence;
- mandar conteúdo privado a provider externo por default;
- routing executar chamadas diretamente.

## Decisão

O AION Core depende de um Model Gateway provider-neutral.

Providers concretos são adapters substituíveis abaixo do gateway.

O registry aceita identidades arbitrárias de provider/model e mantém:
- lane;
- health;
- capabilities;
- priority;
- cost.

Uma implantação certificada deve manter fallback local/offline saudável.

PRIVATE/OFFLINE e external-disabled forçam local.

Budget, health, privacy e capability são gates de elegibilidade.

A decisão de rota não chama provider e não concede execution authority.

## Consequências

O adapter OpenAI atual permanece compatível, mas deixa de ser uma dependência
arquitetural do Core.

Outros providers ou modelos locais podem ser adicionados sem mudar Constitution,
Memory, Multi-Agent Governor ou Policy Kernel.

## Componentes afetados

Model Registry, Model Router, Gateway, Provider adapters, Cost Center, Policy Kernel,
future Execution Gate, offline mode e deployment.

## Segurança

- no provider is authority;
- no provider call in planning;
- private/offline stays local;
- no paid fallback outside budget;
- provider outage degrades/falls back instead of widening permissions;
- local fallback is required for independence certification;
- route-ready is not execution-ready.

## Compatibilidade

`atlasquant_aion_provider.py` permanece como concrete adapter existente. O V2.19
adiciona a fronteira canônica acima dele.

## Rollback/migração

Remover fallback local obrigatório ou acoplar Core a provider específico exige ADR
sucessor e nova certificação.

## PR/commit relacionado

Branch `integration/aion-v219-provider-neutral-model-gateway-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
