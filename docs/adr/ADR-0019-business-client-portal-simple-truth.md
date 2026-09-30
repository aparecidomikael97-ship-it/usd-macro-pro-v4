# ADR-0019 — Portal do Cliente do AION Business deve esconder complexidade e nunca inventar resultado

- Título: Portal do Cliente do AION Business deve esconder complexidade e nunca inventar resultado
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O AION Business já possui Demo, treinamento e simulador de diagnóstico/proposta.
Era necessário fechar a experiência que o futuro cliente enxergará.

## Problema

Expor detalhes técnicos de roteamento, segurança, especialistas e runtime torna
a experiência difícil. Ao mesmo tempo, preencher indicadores sem fonte após uma
demo criaria falsa impressão de resultado real.

## Decisão

Criar um Portal Executivo Demo organizado em Visão Geral, Radar, Plano de Ação,
Resultados, Suporte e Histórico.

A interface mostra contexto, prioridade e próximo passo. Filas, fingerprints,
gates de runtime e demais detalhes ficam internos.

A seção Resultados começa obrigatoriamente em `NO_REAL_RESULTS` e só poderá ser
alimentada futuramente por evidência confiável após implantação e período de
medição.

## Consequências

O cliente terá uma leitura simples da própria operação sem precisar dominar a
tecnologia. O sistema mantém limite claro entre demo e desempenho comprovado.

## Segurança

O Portal Demo não executa contato, contrato, cobrança, publicação, gasto,
deploy ou runtime. Nenhum indicador financeiro é fabricado.

## Compatibilidade

ADR-0018 fornece diagnóstico, Radar e proposta. Este ADR define somente a
experiência read-only derivada desses dados.

## Rollback

O Portal é somente apresentação/session state. Removê-lo não exige compensação
ou migração externa.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
