# ADR-0051 — AION Core carrega o Checkpoint Mestre validado no bootstrap

Título: AION Core carrega o Checkpoint Mestre validado no bootstrap  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O AION precisa conhecer decisões, prioridades e pendências do projeto sem
depender de memória informal ou de o administrador repetir o histórico.

## Problema

Ter o Checkpoint Mestre versionado, mas não conectá-lo ao Core, permite que o
AION opere sem o contexto oficial mais recente.

## Alternativas consideradas

1. Confiar em contexto manual.
2. Criar uma segunda memória paralela.
3. Validar o ponteiro oficial e injetar um snapshot bounded como evidência do Core.

## Decisão

Adotar a alternativa 3.

O Core valida `checkpoint_mestre_latest.json`, carrega o manifesto mais recente
e expõe decisões, pendências, economia, prioridades e papéis multiagente como
evidência interna estável.

Se a validação falhar, nenhuma evidência do Checkpoint Mestre é injetada.

## Consequências

O AION passa a ter um caminho automático e auditável para conhecer a continuidade
oficial, sem duplicar o armazenamento.

## Componentes afetados

- AION Core runtime bridge;
- Checkpoint Mestre;
- evidência do Core;
- Admin AION;
- memória/continuidade.

## Segurança

A ponte é read-only. Não salva checkpoint, não altera runtime, não autoriza
merge/deploy, não chama provider e não executa ações externas.

## Compatibilidade

Reutiliza o validador `atlasquant_aion_checkpoint_latest.py` e preserva a
regra de uma única fonte oficial de continuidade.

## Rollback/migração

A integração pode ser removida sem alterar o conteúdo do Checkpoint Mestre.

## PR/commit relacionado

Draft PR AION Core Master Checkpoint Bootstrap V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
