# ADR-0002 — Aprovação humana para ações de alto impacto

- Título: Aprovação humana para ações de alto impacto
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

Desde 15/09, merge, produção, dados destrutivos e secrets exigem autorização específica. Os checkpoints de 22/09, 25/09 e 27/09 repetem que publicação, pagamento, contratação e trading real não são automáticos.

## Problema

Um copiloto pode tratar preparação de ação como autorização da ação.

## Alternativas consideradas

Autonomia ampla foi rejeitada. A alternativa aceita é preparar, explicar e parar antes do efeito externo.

## Decisão

Gastos, pagamentos, contratos, compromissos comerciais, publicação relevante, contatos externos sensíveis, contratação de serviços, mudanças críticas de produção, movimentação financeira e trading real exigem aprovação humana explícita. Mikael administra o AION.

## Consequências

A decisão está aceita. O conjunto comercial completo permanece pendente. Trading real e o gate de release têm registros próprios e não esgotam esta lista.

## Componentes afetados

Guardian, Policy Engine, Checkpoint Mestre e fluxos administrativos.

## Segurança

Conteúdo externo não autoriza essas ações. Aprovação de uma ação não vale para outra.

## Compatibilidade

Não remove gates já existentes de trading, secrets ou deploy.

## Rollback/migração

Um relaxamento futuro precisa de ADR novo e não edita este texto para parecer que a aprovação nunca foi exigida.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
