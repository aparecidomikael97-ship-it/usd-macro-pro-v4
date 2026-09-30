# AION Core — Master Checkpoint Bootstrap V1

## Objetivo

Fazer o Core conhecer automaticamente o Checkpoint Mestre oficial mais recente.

## Fluxo

1. Ler `checkpoint_mestre_latest.json`.
2. Validar ponteiro, parent binding, budget, papéis e fronteiras fail-closed.
3. Carregar o manifesto incremental.
4. Produzir snapshot bounded.
5. Converter o snapshot em evidência estável do AION Core.
6. Preservar qualquer evidência de runtime já presente.

## Evidências injetadas

- data do checkpoint;
- decisões;
- pendências;
- economia/FinOps/monetização;
- prioridade do ecossistema;
- oito papéis lógicos.

## Fail-closed

Se o ponteiro ou manifesto estiver adulterado, o estado fica
`MASTER_CHECKPOINT_BLOCKED` e nenhuma evidência do checkpoint entra no Core.

## Segurança

A ponte:
- não cria segunda memória;
- não escreve em disco;
- não chama rede;
- não salva runtime;
- não autoriza merge/deploy/runtime;
- não movimenta dinheiro;
- não executa Trade.
