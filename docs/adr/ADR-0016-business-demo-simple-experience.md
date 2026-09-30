# ADR-0016 — AION Business deve apresentar uma experiência simples antes da complexidade técnica

- Título: AION Business deve apresentar uma experiência simples antes da complexidade técnica
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O Business Expert já possui escopo consolidado, certificação, runtime readiness
e sandbox determinístico. A interface histórica de Negócios ainda refletia
principalmente pesquisa de marketplace, o que não representa o novo produto.

## Problema

O administrador e o futuro cliente precisam entender rapidamente o que o AION
Business entrega. Expor primeiro componentes técnicos ou ferramentas legadas
aumenta complexidade e dificulta treinamento, demonstração e venda.

## Decisão

A interface de Negócios passa a apresentar primeiro uma Demo AION Business
organizada em quatro pilares — Atrair, Atender, Converter e Reter — com pacotes,
jornada comercial, Radar do Negócio e trilha de treinamento.

A demo usa somente fixture fictício e marca explicitamente `RUNTIME OFF` e
`SEM AÇÃO EXTERNA`.

A Central Principal também usa essa demo como superfície visual de Negócios.

Ferramentas históricas de marketplace permanecem temporariamente por
compatibilidade, rotuladas como legado e abaixo da experiência principal.

## Consequências

O produto se torna mais fácil de ensinar, demonstrar e avaliar sem remover
componentes históricos de forma arriscada. A interface passa a refletir o escopo
comercial aprovado antes de qualquer ativação operacional.

## Segurança

A demo não autoriza runtime, contato, contrato, pagamento, publicação, gasto,
merge, deploy ou trading real. Dados de exemplo são explicitamente fictícios.

## Compatibilidade

ADR-0012 define o escopo comercial. ADR-0015 define o sandbox. Este ADR define
somente a apresentação da experiência e não altera autoridade operacional.

## Rollback

A remoção da demo volta a superfície anterior sem efeitos externos ou migração
de dados.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
