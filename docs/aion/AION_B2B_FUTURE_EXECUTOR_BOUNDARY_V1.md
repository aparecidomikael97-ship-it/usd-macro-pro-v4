# AION B2B — Future Executor Boundary V1

Status: **design-only / fail-closed / zero executor real**.

## Objetivo

Definir o limite arquitetural que deve existir antes de qualquer futuro contrato
de executor.

Esta camada NÃO cria executor, provider binding, endpoint, payload, credencial,
network call, cobrança, contato, CRM write, deploy ou mutação de produção.

## Condições obrigatórias antes do design avançar

A boundary permanece `BLOCKED` até o código base provar:

1. Adapter V2 possui teto FinOps local e literal de R$200:
   - `FINOPS_CAP_CENTS == 20000`;
   - `FINOPS_CONTRACT_SOURCE == "LOCAL_V2_LITERAL"`;
   - `FINOPS_INPUT_TYPE == "EXACT_INT"`.
2. Adapter V1 está explicitamente marcado:
   - `LEGACY_NON_EXECUTABLE == True`;
   - `EXECUTOR_ELIGIBLE == False`.
3. Entrada é Adapter V2, nunca V1.
4. Receipt continua exclusivamente sintético.
5. Todas as flags de autoridade/efeito continuam false.

## Estado máximo

Mesmo depois de H1/H2 fechados:

`READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW`

O único próximo passo permitido é:

`DESIGN_EXECUTOR_CONTRACT_ONLY`

Isso NÃO significa:
- executor criado;
- provider selecionado;
- comando gerado;
- autorização comercial;
- execução permitida.

O futuro executor real continuará exigindo contrato, red-team e autorização
explícita separados.
