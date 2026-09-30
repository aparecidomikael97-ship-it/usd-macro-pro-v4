# ADR-0053 — Primeira oferta de receita do Business é serviço B2B recorrente com margem e capacidade verificadas

Título: Primeira oferta de receita do Business é serviço B2B recorrente com margem e capacidade verificadas  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O ecossistema precisa priorizar geração de caixa antes de escalar infraestrutura,
IA paga e outras frentes. A estratégia aprovada colocou Negócios como principal
motor inicial de receita.

## Problema

Ter diagnóstico, proposta, onboarding e finanças em módulos separados ainda não
forma uma oferta comercial única com proteção de margem e sequência operacional.

## Alternativas consideradas

1. Vender serviços avulsos sem produto padronizado.
2. Priorizar dropshipping/e-commerce.
3. Produto B2B recorrente com implantação, mensalidade, escopo, custo, margem,
   capacidade e gates explícitos.

## Decisão

Adotar a alternativa 3.

Oferta prioritária:
**AION Atendimento & Automação Comercial**.

Modelo:
- taxa de implantação;
- mensalidade recorrente;
- atendimento/FAQ dentro do escopo;
- qualificação;
- follow-up controlado;
- agendamento/próximo passo;
- radar simples de atendimento e conversão.

O preço final não é hardcoded nem inventado pelo AION. O administrador define a
margem mínima e fornece/valida custos; o sistema calcula contribuição, margem e
piso sustentável.

## Consequências

O Business ganha uma oferta inicial clara, mensurável e compatível com o objetivo
de gerar caixa cedo sem prometer resultado ao cliente.

## Segurança

Mesmo quando todos os gates internos estiverem verdes, o máximo é
`READY_FOR_ADMIN_SALES_REVIEW`.

Não há autorização automática para:
- contato externo;
- envio de proposta;
- assinatura;
- cobrança;
- admissão do cliente;
- runtime.

## Compatibilidade

Reutiliza os módulos existentes de diagnóstico/proposta, capacidade, LGPD,
SLA, onboarding, integrações e FinOps.

## Rollback/migração

A camada é administrativa/read-only; removê-la não altera clientes, preços ou
contratos reais.

## PR/commit relacionado

Draft PR AION BUSINESS B2B Revenue Offer V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
