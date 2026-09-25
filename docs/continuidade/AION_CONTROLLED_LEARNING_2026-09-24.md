# AION — Aprendizado Controlado

Data de consolidação: 2026-09-24

## Objetivo

Fazer o AION evoluir com evidência acumulada sem permitir autoalteração silenciosa
de regras, pesos, produção ou trading real.

## Ciclo oficial

1. Registrar previsão/decisão com assunto, versão, evidências, contexto e confiança.
2. Aguardar o resultado real.
3. Registrar o resultado sem reescrever a previsão original.
4. Medir acerto/erro ou erro numérico.
5. Registrar causa de erro somente quando houver evidência explícita.
6. Calibrar a confiança contra resultados observados.
7. Vincular Backtest, Paper, Forward, Shadow, OOS, calibração e replay por referência.
8. Criar Challenger como hipótese.
9. Exigir evidência fora da amostra, não degradação e Shadow Mode.
10. Tornar o Challenger, no máximo, candidato a revisão humana.
11. Champion continua oficial até aprovação e fluxo de mudança separado.

## Verdade e calibração

- Confiança de previsão não é probabilidade de lucro.
- Taxa histórica observada não é garantia futura.
- Causa sem evidência permanece UNKNOWN.
- O AION não inventa causalidade para explicar erro.
- Aprender mais não significa mudar mais.

## Persistência

O Checkpoint Mestre possui namespace `learning` com:

- `episodes`: diário de previsões e resultados.
- `experiments`: Champion × Challenger.
- `research_refs`: referências para evidências de pesquisa.
- `digest`: integridade do conjunto.

A evidência bruta de backtest não é duplicada no Checkpoint; o diário guarda
referências para os artefatos de pesquisa existentes.

## Travas permanentes

- Autoajuste de pesos: DESATIVADO.
- Mudança automática de regra: DESATIVADA.
- Promoção automática de Challenger: DESATIVADA.
- Mudança automática de produção: DESATIVADA.
- Trading real: BLOQUEADO.
- Pesquisa não altera gate ao vivo automaticamente.

## Estados de experimento

- PLANNED
- RUNNING
- NEED_MORE_EVIDENCE
- REJECTED_FOR_NOW
- HUMAN_REVIEW_CANDIDATE

`HUMAN_REVIEW_CANDIDATE` significa somente que a evidência mínima passou pelo
gate técnico para análise humana; não significa promoção.

## Critérios iniciais Champion × Challenger

O Challenger precisa, no mínimo:

- amostra OOS suficiente;
- melhora mínima de expectancy observada;
- drawdown não pior;
- erro de calibração não pior;
- taxa de falso alerta não pior;
- Shadow Mode elegível para revisão manual;
- zero divergência crítica no Shadow.

Os critérios são auditáveis e podem ser refinados futuramente em Sandbox, mas
não são alterados automaticamente pelo próprio AION.
