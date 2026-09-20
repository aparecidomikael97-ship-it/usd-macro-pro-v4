# AtlasQuant — Research Intelligence Foundation · 20/09/2026

Este bloco transforma decisões aprovadas no roadmap em contratos de pesquisa
auditáveis. Ele não habilita execução real e não declara nenhum operacional
como lucrativo/validado apenas por existir no catálogo.

## 1. Matriz Mestre ICT / SMC / Price Action

Arquivo: `atlasquant_operational_catalog.py`

O catálogo inicial diferencia claramente:

- **CONCEPT** — conceito planejado/documentado;
- **PARTIAL** — componentes existem, mas o replay dedicado ainda não está fechado;
- **CODED** — regras objetivas/replay existem;
- **BACKTESTED** — etapa futura após evidência histórica consolidada;
- **PAPER** — etapa futura após observação fora do backtest;
- **VALIDATED** — somente depois das etapas anteriores e revisão;
- **PAUSED** — pesquisa suspensa.

Os cinco replays objetivos já existentes — BOS/CHOCH+OB, FVG, OTE, CRT e
AMD/PO3 — entram como **CODED**, não como VALIDATED. Silver Bullet, Turtle
Soup, Unicorn, Judas, MMXM, Weekly Profile, Quarterly Theory e modelos de Price
Action entram como conceito/parcial conforme o estado real do repositório.

O catálogo é propositalmente **não exaustivo**. A auditoria de ICT/SMC seguirá
expandindo a lista antes de qualquer declaração de cobertura completa.

## 2. Decision Stack + Auditor de Confluência

Arquivo: `atlasquant_decision_stack.py`

Camadas oficiais:

1. Fundamental/Macro;
2. SMC;
3. ICT;
4. Price Action;
5. Safety.

Cada evidência possui `source_family`. Quando SMC, ICT e Price Action estão
descrevendo o mesmo evento de preço, somente a evidência mais forte daquela
família é contada. Isso evita double counting.

O motor também expõe conflito entre camadas e veto do Safety. O estado
`CONFLICT_REVIEW` não é convertido em falsa certeza, e
`BLOCKED_BY_SAFETY` continua bloqueado independentemente do alinhamento
restante.

O `alignment_index` é descritivo; **não é probabilidade de lucro**.

## 3. Diagnóstico Pós-Operação

Arquivo: `atlasquant_post_trade_diagnosis.py`

Objetivo: investigar por que um gain/loss aconteceu sem usar informação futura.

Regras:

- snapshot pré-trade precisa ter sido capturado antes da entrada;
- notícia/evento durante a operação é separado do que já era conhecido antes;
- evento posterior à saída é ignorado para aquele diagnóstico;
- macro, confirmação técnica, liquidez, regime, qualidade dos dados, plano,
  evento, custos e slippage são registrados como fatores;
- gain com decisão fraca é separado de gain com decisão coerente;
- loss com decisão coerente é separado de loss com falhas identificadas;
- causas são apresentadas como fatores/evidências **prováveis**, nunca como
  causalidade comprovada quando os dados não permitem.

## 4. Passaporte do Operacional

Arquivo: `atlasquant_operational_passport.py`

O Passaporte organiza:

- trades e métricas históricas;
- expectancy, profit factor, net R e drawdown;
- cobertura de ativos, sessões e regimes;
- amostra paper;
- diferença paper × backtest;
- qualidade dos dados;
- última validação;
- lacunas de evidência.

Mesmo quando todos os critérios estão preenchidos, o resultado máximo desta
fundação é `eligible_for_human_review=True`. Promoção automática permanece
desativada.

## 5. Perfil Semanal Estatístico

Arquivo: `atlasquant_weekly_profile.py`

Mede em qual dia o high e o low semanais realmente se formaram na amostra.
Inclui a frequência terça/quarta para testar a hipótese discutida, mas
`fixed_day_rule_assumed=False`.

A leitura deve ser segmentada futuramente por ativo, sessão, regime e período.
Ela não afirma que grandes instituições sempre formam o extremo da semana em
um dia específico.

## 6. Detector de Mudança de Comportamento

Arquivo: `atlasquant_behavior_shift.py`

Compara janela histórica × janela recente usando proxies observáveis:

- expansão Londres;
- expansão Nova York;
- follow-through após sweep;
- reversão após sweep;
- reação em níveis mapeados;
- range médio.

Amostras pequenas retornam `INSUFFICIENT_SAMPLE`. Mudanças relevantes geram
sinal de revisão, nunca alteração automática do operacional.

O módulo declara explicitamente:

- `institutional_intent_inferred=False`;
- `automatic_strategy_change=False`.

## Próximas integrações

1. ligar o catálogo ao Laboratório de Backtest;
2. adicionar o diagnóstico gain/loss ao ledger e ao painel;
3. alimentar o Passaporte com backtest + walk-forward + shadow + paper;
4. segmentar Weekly Profile por ativo/regime;
5. alimentar o detector de comportamento com histórico persistido;
6. apresentar os resultados no Copiloto/Admin;
7. somente depois criar vídeos da Academy para versões realmente testadas.

Roadmap mestre relacionado: issue #51.
