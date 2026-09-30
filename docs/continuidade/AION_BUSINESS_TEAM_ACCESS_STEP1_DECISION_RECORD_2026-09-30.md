# Continuidade — Explicit Step 1 Decision Record — 30/09/2026

## Estado

Implementado / em validação sobre a Draft PR #464.

## Entrega

- token formal específico do Step 1;
- generic language não autoriza;
- binding ao step1 packet digest;
- target order/id fixos;
- packet age máximo de 300 s;
- observation age máximo de 900 s;
- decided_by preso ao observador do packet;
- acknowledgements completos;
- decision record digest;
- verifier de binding;
- CLI local;
- template JSON;
- ADR-0077.

## Estado máximo

EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED

## Não ocorreu

- nenhuma decisão real foi registrada;
- nenhum Step 1 foi executado;
- nenhuma conta foi criada;
- nenhum receipt foi produzido;
- nenhum ledger append ocorreu;
- executor/produção/deploy/runtime seguem OFF.

## Próximo gate

Somente depois de um decision record real válido poderá existir um execution
envelope manual para o Step 1. Esse envelope deverá continuar separado da
execução física.
