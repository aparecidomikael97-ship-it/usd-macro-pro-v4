# ADR-0054 — Primeiro piloto B2B exige fit, preço sustentável e Pilot Governance antes de revisão administrativa

Título: Primeiro piloto B2B exige fit, preço sustentável e Pilot Governance antes de revisão administrativa  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

A oferta B2B inicial já está productizada e o projeto precisa avançar em direção
ao primeiro piloto sem escolher cliente ou preço de forma arbitrária.

## Problema

Mesmo com uma oferta pronta internamente, um primeiro piloto inadequado pode
consumir suporte, ter margem ruim, gerar risco de privacidade ou criar falsa
sensação de validação.

## Alternativas consideradas

1. Escolher o primeiro interessado e testar.
2. Definir um preço promocional automático.
3. Exigir fit explícito, preço sustentável, oferta pronta e Pilot Governance.

## Decisão

Adotar a alternativa 3.

A revisão do primeiro piloto exige:
- referência e segmento explícitos;
- fit mensurado a partir de entradas administrativas;
- piso de fit definido pelo administrador;
- permissão de contato não bloqueada;
- preço de piloto acima do piso sustentável da oferta;
- margem mínima preservada;
- taxa de implantação cobrindo seu custo;
- oferta em READY_FOR_ADMIN_SALES_REVIEW;
- Pilot Governance com gates completos;
- packet de aprovação humana ainda não autorizado.

O máximo automático é `READY_FOR_ADMIN_FIRST_PILOT_REVIEW`.

## Consequências

O AION pode organizar evidência e dizer se o candidato está pronto para revisão,
mas não escolhe cliente, preço ou início do piloto sozinho.

## Segurança

A camada não autoriza:
- contato;
- envio de proposta;
- assinatura;
- cobrança;
- admissão de tenant;
- runtime;
- deploy;
- publicação.

## Compatibilidade

Reutiliza a oferta B2B V1 e o Pilot Governance V1 existentes.

## Rollback/migração

Read-only. Remoção não altera cliente, preço ou produção.

## PR/commit relacionado

Draft PR AION BUSINESS First Pilot & Pricing Review V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
