# ADR-0021 — Customer Success precede upsell no AION Business

- Título: Customer Success precede upsell no AION Business
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O fluxo Business já cobre diagnóstico, proposta, Portal e onboarding. Para
sustentar receita recorrente, faltava formalizar o acompanhamento pós-implantação.

## Problema

Se o sistema sugerir expansão ou renovação sem considerar adoção, incidentes,
objetivos e satisfação, a operação pode priorizar receita de curto prazo em vez
de valor entregue ao cliente.

## Decisão

Criar uma camada de Customer Success com health score, plano de sucesso, SLA,
renovação e expansão.

Clientes demonstrativamente em risco recebem prioridade de recuperação. Upsell
só pode aparecer como oportunidade de revisão quando o health state é saudável e
há sinais de adoção, progresso e satisfação.

Nenhuma expansão ou renovação é automática.

## Consequências

A operação recorrente passa a incorporar retenção e saúde do cliente como parte
do produto, não apenas como métrica comercial.

## Segurança

O demo não contata, cobra, renova, publica ou modifica produção. Tickets e
inadimplência são apenas fixtures.

## Compatibilidade

ADR-0020 define onboarding/implantação. Este ADR cobre o ciclo posterior à
entrega assistida.

## Rollback

O módulo é read-only/session state e pode ser removido sem compensação externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
