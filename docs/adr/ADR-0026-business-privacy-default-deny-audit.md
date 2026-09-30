# ADR-0026 — AION Business deve aplicar purpose limitation, default deny e trilha auditável

- Título: AION Business deve aplicar purpose limitation, default deny e trilha auditável
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Business futuramente poderá tratar dados de leads, clientes, agendas,
suporte, métricas e integrações.

## Problema

Sem finalidade, retenção, controle por perfil e auditoria, uma automação pode
acessar mais dados do que precisa, manter dados por tempo indefinido ou executar
mudanças sem rastreabilidade.

## Decisão

Criar uma camada de governança que exige:

- finalidade;
- categorias de dados;
- base jurídica para revisão;
- retenção;
- consentimento quando aplicável;
- default deny;
- least privilege;
- solicitações de export/delete/correct/restrict em review-only;
- trilha de auditoria;
- versionamento;
- rollback preparado com aprovação humana.

## Consequências

Privacidade e auditoria deixam de ser documentação lateral e passam a fazer parte
do fluxo operacional do Business.

## Limite jurídico

O módulo não substitui orientação jurídica e não determina sozinho a base legal
aplicável a uma empresa real.

## Segurança

Nenhuma exclusão, exportação, mudança externa ou rollback de produção é
executado automaticamente.

## Compatibilidade

ADR-0025 protege integrações e segredos. Este ADR protege finalidade, acesso e
rastreabilidade dos dados que essas integrações poderão usar futuramente.

## Rollback

Camada offline/readiness; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
