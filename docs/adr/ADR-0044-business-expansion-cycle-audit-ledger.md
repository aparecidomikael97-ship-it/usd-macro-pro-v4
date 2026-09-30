# ADR-0044 — Ciclos de expansão usam ledger encadeado e anti-replay

- Título: Ciclos de expansão usam ledger encadeado e anti-replay
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0043 encerra cada expansão verificada congelando novamente o escopo.

## Problema

Sem histórico encadeado, um receipt antigo poderia ser reapresentado, a
continuidade entre ciclos poderia ser perdida e a trilha de auditoria ficaria
fragmentada.

## Decisão

Criar um ledger administrativo puro para registrar apenas ciclos já verificados
e congelados.

Cada entrada registra:

1. sequência;
2. digest da entrada anterior;
3. digest da verificação de expansão;
4. digest da autorização;
5. escopo e tenants anteriores;
6. escopo e tenants verificados;
7. digest próprio da entrada.

O ledger começa vinculado a um boundary de gênese já verificado. Sem essa âncora, o estado é `EXPANSION_CYCLE_LEDGER_GENESIS_REQUIRED` e nenhum ciclo pode ser anexado. Isso impede truncar o começo do histórico e apresentar uma sequência parcial como completa.

O ledger revalida:

- integridade da cadeia;
- sequência;
- ausência de replay;
- progressão válida;
- preservação de tenants;
- continuidade exata entre o fim de um ciclo e o início do próximo;
- limite de 10 tenants;
- flags operacionais permanentemente false.

## Consequências

A história de expansão passa a ser auditável e tamper-evident. Qualquer drift,
replay ou corrupção bloqueia o append.

## Segurança

O ledger não executa expansão, runtime, deploy, rollback, publicação, cobrança
ou comunicação com clientes.

## Compatibilidade

A entrada aceita somente receipts do schema definido por ADR-0043.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
