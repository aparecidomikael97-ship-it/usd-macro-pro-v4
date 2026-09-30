# ADR-0038 — Deploy e runtime do AION Business são decisões independentes

- Título: Deploy e runtime do AION Business são decisões independentes
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

Depois do acknowledgement técnico da consolidação, ainda é necessário definir
como o sistema chega a um ambiente sem transformar deploy em ativação automática.

## Problema

Um deploy tecnicamente autorizado pode ser confundido com permissão para ligar
runtime, atender cliente real, publicar ou cobrar.

## Decisão

Criar um handoff explícito entre consolidação e deploy.

O handoff exige plano de deploy, rollback, monitoramento, ambiente alvo e runtime
BUSINESS OFF.

O máximo automático é `READY_FOR_SEPARATE_DEPLOY_DECISION`.

Uma futura decisão de deploy deverá usar o token
`AUTHORIZE_BUSINESS_DEPLOY_ONLY` e reconhecer explicitamente que runtime é uma
decisão posterior e separada.

## Consequências

A cadeia de autoridade fica:

consolidação técnica → acknowledgement técnico → decisão de deploy →
deploy verificado → decisão de runtime.

Nenhuma seta é automática.

## Segurança

O módulo não autoriza nem executa deploy/runtime.

## Compatibilidade

ADR-0037 fecha a consolidação técnica. Este ADR define a fronteira seguinte.

## Rollback

Módulo read-only; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
