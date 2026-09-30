# ADR-0027 — DEMO, PILOT e LIVE são autoridades distintas no AION Business

- Título: DEMO, PILOT e LIVE são autoridades distintas no AION Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A aba Negócios acumulou vários módulos validados em modo demo. Era necessário
evitar que "muita coisa pronta" fosse interpretada como autorização para atender
cliente real ou ligar runtime.

## Problema

Sem uma separação explícita, UI pronta, testes verdes ou certificação podem ser
confundidos com autorização operacional.

## Decisão

Criar um Painel Mestre com três camadas independentes:

- DEMO: produto e experiência validados em ambiente controlado;
- PILOT: revisão separada de operação com cliente controlado;
- LIVE: autoridade operacional e runtime real.

Nenhuma camada herda automaticamente a autoridade da anterior.

## Consequências

O administrador consegue ver avanço rapidamente sem perder o limite de
segurança entre demonstração e operação.

## Segurança

DEMO completo não autoriza PILOT. PILOT elegível não autoriza PILOT. LIVE gates
completos não ativam runtime automaticamente.

## Compatibilidade

ADR-0012–0026 continuam definindo os módulos e seus limites. Este ADR apenas os
consolida numa visão de autoridade.

## Rollback

Painel agregador/read-only; sem efeito externo.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
