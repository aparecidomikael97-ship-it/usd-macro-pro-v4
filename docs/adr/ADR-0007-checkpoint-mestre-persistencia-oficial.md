# ADR-0007 — Checkpoint Mestre como persistência oficial

- Título: Checkpoint Mestre como persistência oficial
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

CORE_CHECKPOINT_MEMORY.md liga a memória do Core ao Checkpoint Mestre e recusa um segundo sistema remoto. O salvamento externo continua explícito.

## Problema

Memória de conversa, banco paralelo ou gravação automática poderiam substituir o checkpoint sem deixar histórico.

## Alternativas consideradas

Store paralelo automático foi rejeitado. A alternativa aceita é namespace dentro do Checkpoint Mestre, com digest e aprovação humana para persistência remota.

## Decisão

O Checkpoint Mestre é a persistência oficial. Não há store paralelo automático. O documento de 22/09/2026 permanece; a reconciliação de 29/09 o complementa.

## Consequências

Staging local não é persistência remota. Integridade divergente bloqueia o save. Esta ADR não declara o checkpoint de produção verificado.

## Componentes afetados

atlasquant_aion_memory.py; fluxo Salvar Checkpoint Mestre no runtime.

## Segurança

Recibo de aprovação é de uso único e não autoriza execução física, publicação, pagamento, deploy ou mercado.

## Compatibilidade

Checkpoints antigos continuam migráveis em memória sem serem declarados persistidos.

## Rollback/migração

Introduzir outro store exige ADR que marque este como SUPERSEDED e aponte o sucessor. O arquivo não é apagado.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
