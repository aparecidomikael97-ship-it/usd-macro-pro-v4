# AION BUSINESS Capacity & Scale Manager V1

## Objetivo

Responder com evidência a perguntas como:

- quantas empresas novas cabem hoje?
- o orçamento atual comporta mais um cliente?
- suporte e infraestrutura ainda têm folga?
- a margem de um novo contrato é suficiente?
- existe algum tenant atual que precisa ser estabilizado antes de crescer?

## Entradas

- capacity/quota review íntegro;
- métricas atuais por tenant;
- custo compartilhado da plataforma;
- teto mensal aprovado;
- horas de suporte disponíveis;
- carga de suporte estimada por novo tenant;
- headroom de infraestrutura;
- carga de infraestrutura estimada por novo tenant;
- custo estimado por novo tenant;
- receita esperada por novo tenant.

## Teto inicial

Nesta versão o teto aprovado não pode exceder **R$200/mês**.

## Bloqueios

Crescimento é bloqueado quando:
- plano de quotas foi adulterado;
- conjunto de tenants não bate;
- tenant atual passa de 85% de utilização;
- existe incidente de alta severidade;
- margem mínima não é atingida;
- não há orçamento;
- não há suporte;
- não há infraestrutura;
- não há slot dentro do limite de 10 tenants.

## Saída

`safe_additional_tenants` informa o menor número seguro entre todos os
recursos.

Mesmo com capacidade positiva, o próximo estado é somente
`EXPLICIT_CUSTOMER_ADMISSION_DECISION_REQUIRED`.

Nenhum cliente é admitido automaticamente.
