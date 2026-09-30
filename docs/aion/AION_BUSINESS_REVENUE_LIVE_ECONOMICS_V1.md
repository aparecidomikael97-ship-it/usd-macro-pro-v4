# AION BUSINESS — Revenue Live Economics Binding V1

## Objetivo

Tirar dois inputs críticos do campo manual:

- **custo mensal** passa a vir do ledger FinOps verificado;
- **capacity_ready** passa a vir do Capacity Manager com métricas reais.

Preço e startup budget continuam decisões administrativas.

## Custo real por oportunidade

O administrador seleciona entradas do ledger por `entry_id` e informa um
percentual de alocação para cada uma.

Exemplo conceitual:
- 50% de uma entrada de IA;
- 25% de uma entrada de hosting.

O sistema calcula:
`allocated_cost = source_amount × allocation_pct`

A soma vira `estimated_monthly_cost_brl` da oportunidade.

## Proteções

- ledger precisa estar íntegro;
- entry_id precisa existir;
- apenas custo recorrente entra no custo mensal;
- alocação precisa ser >0 e <=100%;
- alteração no ledger quebra a verificação;
- nenhuma escrita no ledger.

## Capacidade real

A oportunidade só recebe `capacity_ready=true` quando o binding de capacidade
está em `LIVE_CAPACITY_REVIEW_READY` e há pelo menos um tenant adicional seguro.

## Engine único

O binding reutiliza:
- `evaluate_revenue_opportunity()`;
- `rank_revenue_opportunities()`.

Não existe segundo ranking paralelo.

## O que continua administrativo

- monthly_price_brl;
- available_startup_budget_brl;
- startup_cost_brl;
- implementation_days;
- minimum_margin_pct;
- repeatability;
- evidence readiness;
- support load;
- implementation complexity.

## Autoridade

O máximo é:
`READY_FOR_ADMIN_LIVE_REVENUE_PRIORITY_REVIEW`.

Isso não autoriza:
- venda;
- preço;
- gasto;
- contato;
- cobrança;
- admissão de cliente.
