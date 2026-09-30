# ADR-0023 — Tendências e melhoria contínua do AION Business exigem evidência e experimento

- Título: Tendências e melhoria contínua do AION Business exigem evidência e experimento
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Business deve buscar tendências continuamente e melhorar com o tempo, sem
se tornar um sistema que muda, publica ou vende qualquer novidade sem validação.

## Problema

"Buscar tendências" sem proveniência pode confundir moda, opinião e evidência.
"Aprender sozinho" sem gates pode promover regressões ou alterar produção sem
controle.

## Decisão

Formalizar o ciclo:

Observar → Validar → Testar → Medir → Revisar → Promover.

Toda oportunidade recebe score e estado de verdade. Evidência precisa ser
identificada, recente e confiável. Evidência insuficiente ou stale falha fechada.

Melhorias precisam de hipótese, métrica, antes/depois e amostra mínima.
`IMPROVEMENT_SUPPORTED` nunca faz auto-deploy ou auto-promoção.

## Consequências

O AION pode evoluir continuamente sem tratar novidade como verdade nem resultado
como causalidade automática.

## Segurança

Nenhuma tendência autoriza gasto, publicação, contato, deploy, mudança de
produção ou runtime.

## Compatibilidade

ADR-0022 protege margem/capacidade por cliente. Este ADR acrescenta a camada de
oportunidade e aprendizado controlado que alimenta futuras decisões comerciais.

## Rollback

O módulo é analítico e offline. Sua remoção não exige compensação externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
