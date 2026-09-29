# AION Core Loop Governor V1

Data: 2026-09-29
Base: `cursor/aion-core-model-registry-v1` @ `c30044bbf1a38e068ca32a94c151adbcca786324`

`atlasquant_aion_loop_governor.py` limita um plano multiagente antes de qualquer execução. Profundidade, fan-out e quantidade de nós têm teto. O orçamento de recurso continua em `resource_governor`. O modo de cada nó continua em `autonomy_budget`.

O plano só fica `WITHIN_LIMITS` quando a estrutura é uma árvore alcançável, o escopo bate com o contexto confiável, nenhum nó está `BLOCKED` ou `ADMIN_REQUIRED`, e o governor de recurso autoriza trabalho sensível novo. Mesmo nesse estado, `grants_permission`, `executes_action` e `starts_worker` ficam falsos.

Limite que não é `int` positivo, inclusive `"true"`, `1.5` e `True`, bloqueia. Pedido acima do teto é cortado no teto, não atendido. Texto no nó não concede papel nem permissão.

Este contrato não é chamado pelo worker global.
