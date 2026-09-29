# ADR-0005 — Especialistas compartilham o Core sem permissão independente

- Título: Especialistas compartilham o Core sem permissão independente
- Data: 2026-09-29
- Status: ACCEPTED

## Contexto

ARCHITECTURE.md lista especialistas que compartilham infraestrutura. ADDING_CAPABILITIES.md diz que o especialista não recebe permissão própria e não executa fora do Guardian.

## Problema

Cada especialista poderia carregar credencial, flag de trading ou direito de publicação próprio.

## Alternativas consideradas

Permissões independentes foram rejeitadas. Capabilities continuam declarando papel, risco e ferramenta, sob o mesmo Guardian.

## Decisão

Especialistas compartilham o Core. Nenhum deles ganha permissão independente. Specialist Router futuro não pode autoelevar domínio.

## Consequências

O registry atual de especialistas permanece. Novos experts de Trader, Negócios e Investimentos só entram sob esta regra.

## Componentes afetados

atlasquant_aion_specialists.py; Capability Registry; Guardian.

## Segurança

real_trade continua negado mesmo com aprovação. Ferramenta desconhecida falha fechada.

## Compatibilidade

Não cria um segundo núcleo de permissão.

## Rollback/migração

Se um especialista precisar de direito novo, o direito nasce no Core/Guardian e fica registrado em ADR. Este arquivo não é apagado.

## PR/commit relacionado

Nenhum PR deste registro é citado como prova de produção. Evidência por caminho de arquivo, sem SHA de deploy.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
