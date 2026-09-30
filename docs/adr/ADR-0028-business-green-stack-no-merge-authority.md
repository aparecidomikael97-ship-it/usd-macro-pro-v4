# ADR-0028 — Stack verde não concede autoridade de merge no AION Business

- Título: Stack verde não concede autoridade de merge no AION Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

A evolução do AION Business passou a existir em uma stack de Draft PRs
encadeadas, com checks verdes e limites de segurança explícitos.

## Problema

Muitas PRs verdes podem ser interpretadas incorretamente como autorização para
merge, deploy ou runtime.

## Decisão

Criar um manifest congelado da stack #398–#411 e separar quatro conceitos:

1. stack tecnicamente coerente;
2. pronta para revisão administrativa;
3. merge explicitamente autorizado;
4. deploy/runtime explicitamente autorizados.

O estado máximo produzido automaticamente pelo módulo é
`READY_FOR_ADMIN_REVIEW`.

## Ordem

A ordem técnica prevista para uma eventual consolidação é stacked order, da PR
mais antiga para a mais nova.

A ordem prevista não concede autorização para executar o merge.

## Pós-merge

Mesmo após uma futura autorização de merge, a main precisa de:

- CI final;
- verificação do SHA final;
- revisão de regressões;
- verificação da postura de runtime.

## Consequências

A equipe pode consolidar muito trabalho sem transformar CI verde em permissão
operacional implícita.

## Segurança

O manifest não executa merge, rebase, deploy, publicação, pagamento, contato ou
runtime.

## Compatibilidade

ADR-0027 separa DEMO/PILOT/LIVE. Este ADR separa prontidão técnica de autoridade
administrativa de merge.

## Rollback

Camada read-only/offline; sem efeito externo.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
