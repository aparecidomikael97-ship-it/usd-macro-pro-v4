# AtlasQuant — candidatos explícitos por modelo · 20/09/2026

Este bloco cria a ponte segura entre os detectores ICT existentes e a futura
coleta Paper específica por operacional.

## Problema resolvido

O scanner já detecta CRT, OTE, AMD/PO3 e FVG. Porém um trade genérico não pode
ser classificado retrospectivamente como "FVG", "OTE" etc. depois de sabermos
se deu gain ou loss.

Agora cada detector pode gerar um **candidato de pesquisa explicitamente
atribuído pelo modelo de origem no instante da captura**.

## Módulo

Arquivo:

- `atlasquant_setup_candidates.py`

Modelos iniciais:

- CRT → `setup_id=crt`;
- OTE → `setup_id=ote`;
- AMD/PO3 → `setup_id=amd-po3`;
- FVG → `setup_id=fvg`.

## Quando vira candidato

O contrato inicial é conservador:

- CRT: somente `CRT CONFIRMADO`;
- OTE: somente `DENTRO DO OTE`;
- AMD/PO3: somente fase de distribuição confirmada;
- FVG: somente `FVG EM TESTE`.

Estados amarelos/de preparação continuam registrados no pacote dos modelos,
mas não entram em `candidates`.

## Autopilot

O Autopilot grava em cada snapshot ICT:

- `setup_candidates.models` — estado dos quatro modelos;
- `setup_candidates.candidates` — somente candidatos confirmados;
- candidate_id determinístico;
- pair, side, captured_at;
- setup_id e source_model;
- evidência observável do detector.

A atribuição é `SOURCE_MODEL_EXPLICIT`.

## O que isto NÃO faz

Um candidato:

- não cria trade Paper;
- não cria ordem real;
- não altera Gate;
- não promove setup;
- não escolhe vencedor;
- não é recomendação;
- não é probabilidade de lucro.

Campos de segurança permanecem explicitamente falsos:
`automatic_paper_entry=False`, `automatic_execution=False`,
`real_orders_enabled=False`.

## Por que separar candidato de trade

A próxima etapa poderá criar um Paper específico por operacional preservando a
identidade do modelo desde o nascimento do sinal. Assim, Backtest × Paper pode
ser comparado sem olhar o resultado para decidir qual setup "era" aquela
operação.

Isso também permite segmentar cada modelo por ativo, sessão e regime, requisito
necessário para o futuro Radar por disponibilidade de horário.
