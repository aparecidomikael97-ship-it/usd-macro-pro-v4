# ADR-0022 — Financeiro por cliente do AION Business deve separar receita, custo, margem e capacidade

- Título: Financeiro por cliente do AION Business deve separar receita, custo, margem e capacidade
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O ciclo Business agora cobre aquisição, proposta, implantação e Customer Success.
Para proteger rentabilidade recorrente, faltava visibilidade econômica por
cliente e consumo operacional.

## Problema

Olhar apenas faturamento mascara custos de IA, integrações, suporte, ferramentas,
impostos e capacidade. Isso pode transformar crescimento de clientes em perda
de margem ou sobrecarga.

## Decisão

Adicionar uma Central Financeira por Cliente com separação obrigatória entre
receita, custos, contribuição e margem, além de quotas de requisições e suporte.

Nenhum valor de reinvestimento é inferido automaticamente neste módulo.

Margem baixa, margem negativa, capacidade elevada ou inadimplência apenas geram
revisão humana. Não existe reajuste ou cobrança automática.

## Consequências

O AION Business passa a medir não só quantidade de clientes, mas qualidade
econômica e capacidade de atendimento de cada cliente.

## Segurança

O módulo não emite invoice, não cobra, não movimenta dinheiro e não ativa
runtime.

## Compatibilidade

ADR-0021 define saúde e retenção do cliente. Este ADR acrescenta a dimensão
financeira e de capacidade por cliente.

## Rollback

Read-only/session state; sem compensação externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
