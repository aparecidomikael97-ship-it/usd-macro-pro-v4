# AION BUSINESS Client Finance Demo V1

Schema: `ATLASQUANT_AION_BUSINESS_CLIENT_FINANCE_DEMO_V1`

## Objetivo

Dar visibilidade econômica por cliente sem confundir faturamento, lucro e caixa.

## Entradas do demo

- receita de implantação;
- receita mensal recorrente;
- custo de IA;
- custo de integrações;
- suporte;
- ferramentas;
- impostos estimados;
- outros custos;
- estado de pagamento fictício;
- uso mensal e quota;
- horas de suporte e quota.

## Regras financeiras

A interface separa explicitamente:

- receita mensal;
- custos mensais;
- contribuição mensal;
- margem percentual.

Receita nunca é apresentada como lucro.

`available_for_reinvestment` permanece `NOT_CALCULATED_HERE`; o módulo por
cliente não decide sozinho quanto pode ser reinvestido.

## Capacidade

O demo acompanha utilização de requisições e suporte para detectar:

- HEALTHY;
- WATCH;
- AT_LIMIT;
- UNKNOWN.

Isso ajuda a evitar sobrecarga e proteger margem antes de ampliar o cliente.

## Revisão comercial

Margem negativa, margem muito fina, capacidade elevada ou inadimplência demo
podem produzir revisão comercial.

Nenhum reajuste ou cobrança ocorre automaticamente.

## Portfólio

O módulo também suporta agregação demo de:

- MRR/receita mensal;
- custos;
- contribuição;
- clientes com margem negativa;
- clientes próximos do limite;
- inadimplência fictícia.

## Segurança

- nenhum invoice;
- nenhuma cobrança;
- nenhuma movimentação financeira;
- nenhum dado contábil real presumido;
- nenhum runtime;
- nenhuma publicação ou deploy.
