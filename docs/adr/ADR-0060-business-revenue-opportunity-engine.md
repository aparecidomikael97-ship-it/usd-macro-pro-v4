# ADR-0060 — Oportunidades de Receita são priorizadas por viabilidade econômica antes de score

Título: Oportunidades de Receita são priorizadas por viabilidade econômica antes de score  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

A aba Negócios precisa decidir onde concentrar esforço comercial sem cair em
achismo ou perseguir ideias que parecem atraentes, mas estouram custo, margem ou
capacidade.

## Problema

Um ranking puramente qualitativo pode premiar oportunidades rápidas, porém
economicamente inviáveis. Também seria incorreto apresentar um score interno
como probabilidade de venda.

## Alternativas consideradas

1. Escolha manual sem estrutura.
2. Ranking direto de todas as ideias.
3. Gate econômico primeiro e score comparativo depois.

## Decisão

Adotar a alternativa 3.

Uma oportunidade é bloqueada antes do ranking se:
- startup cost excede orçamento disponível;
- margem fica abaixo do piso administrativo;
- contribuição mensal não é positiva;
- capacidade não está pronta;
- inputs obrigatórios estão incompletos.

Somente oportunidades elegíveis recebem score, formado por:
- margem;
- velocidade potencial para entrar em operação;
- repetibilidade;
- evidência disponível;
- eficiência de startup;
- carga de suporte;
- complexidade de implantação.

O score é planejamento e não probabilidade, previsão de venda ou garantia.

## Consequências

O AION pode ordenar oportunidades com base em inputs explícitos e mostrar quais
foram bloqueadas e por quê.

## Segurança

A camada não:
- vende;
- contata;
- gasta;
- altera preço;
- publica;
- cobra;
- provisiona tenant;
- ativa runtime.

## Compatibilidade

Compatível com a estratégia service-first B2B e com FinOps/Capacidade.

## PR/commit relacionado

Draft PR AION BUSINESS Revenue Opportunity Engine V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
