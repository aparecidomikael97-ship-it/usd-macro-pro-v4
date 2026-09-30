# AION BUSINESS — Equipe & Acessos · Step 1 Execution Envelope V1

## Objetivo

Preparar a última fronteira read-only antes de um apply manual do Step 1.

## Inputs

- lifecycle materialization;
- Step 1 preflight packet;
- Step 1 verified decision record;
- observação pós-decisão.

## Observação pós-decisão

Use uma cópia local de:

    deploy/sandbox/team-access/step1-execution-observation.template.json

A observação precisa confirmar, por leitura:

- target account ainda ausente;
- identity provider lookup executado em modo read-only;
- tenant scope correto;
- sandbox/OIDC/registry saudáveis;
- secrets locais;
- ausência de produção;
- cleanup pronto.

A observação precisa ser posterior à decisão.

## Janela

No momento de preparar o envelope:

- decisão: até 120 segundos;
- observação pós-decisão: até 120 segundos.

## CLI

    python build_team_access_step1_execution_envelope.py <materialization.json> <step1-packet.json> <verified-step1-decision.json> <execution-observation.json> --output <step1-execution-envelope.json>

## Estado máximo

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY

O CLI não gera comando de provider e não cria a conta.
