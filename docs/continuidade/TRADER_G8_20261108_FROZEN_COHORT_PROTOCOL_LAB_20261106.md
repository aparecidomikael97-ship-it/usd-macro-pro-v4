# AtlasQuant Trader — coorte prospectiva congelada G8/28, 08/11/2026 (LAB)

## Avanço real do protocolo

Antes de escolher pares supostamente vencedores, registramos um **universo fixo de pesquisa**: os 28 pares Forex G8 × dois horizontes (D1 e W1) = **56 vagas de avaliação**. O arquivo JSON estático `TRADER_G8_20261108_D1W1_FROZEN_COHORT_LAB.json` fica nesta pasta do laboratório e faz parte de um commit na PR #1815; há código gerador e verificador reproduzíveis, respectivamente `atlasquant_trader_fx_g8_frozen_cohort_lab.py` e `test_atlasquant_trader_fx_g8_frozen_cohort_lab.py`.

**Importante:** congelar um conjunto de estudos é diferente de congelar previsões. **As 56 vagas estão SEM PREVISÃO**, e não existem 56 sinais nem 56 resultados. Toda `direction`, `forecast_receipt_sha256` e `independent_precommit_witness` é `null`. A revisão não transforma `AGUARDAR` em ganho e não considera posições neutras acertos direcionais.

O instante `planning_reference_utc_claim=2026-11-06T13:50:00Z` é apenas o **instante de referência usado para calcular as próximas janelas**. Ele **não é alegação comprovada da hora de criação** do arquivo ou da previsão. O commit do GitHub poderá ser consultado externamente, mas metadata de commit e branch mutável, sozinhas, não provam que uma previsão com resultado real estava registrada antes da negociação. Esta coorte não contém direções.

## As primeiras duas janelas fixadas

| Horizonte | Abertura convencional NY 17h | Encerramento | Limite para compromisso antes da sessão |
|---|---|---|---|
| D1 | Domingo 08/11/2026 22h UTC | Segunda 09/11/2026 22h UTC | Domingo 08/11/2026 21h UTC |
| W1 | Domingo 08/11/2026 22h UTC | Sexta 13/11/2026 22h UTC | Domingo 08/11/2026 21h UTC |

O cálculo usa o fuso IANA `America/New_York`, inclusive a alternância EDT/EST. São **janelas de pesquisa**, não horários comprovados do servidor da corretora, nem autorização para iniciar ordens.

## Política contra seleção de vencedores

O protocolo exige que **todo slot permaneça visível**, inclusive em caso de abstenção `NEUTRO/AGUARDAR`, dado ausente, divergência ou resultado indisponível. Mais tarde, os resultados poderão ser avaliados em separado por horizonte, denominador de previsões executáveis e abstenções. Um par sem histórico M15 válido **não será classificado como acerto**, nem excluído silenciosamente da cobertura.

A função `inspect_g8_forward_cohort_lab(raw, inspected_at_utc=...)` compara os **bytes inteiros** com uma reconstrução canônica dos 28 pares e 56 slots. Rejeita símbolo removido/alterado, período invertido, campos de previsão preenchidos no plano, alteração de prazos, mudança na política de abstenções ou serialização diferente. O hash SHA-256 identifica os bytes, não comprova proveniência e nem imutabilidade jurídica. Depois do limite para pré-registro, o verificador informa que é tarde para criar **novos compromissos prospectivos** daquela sessão.

## O que falta, sem exceção

1. Dados macroeconômicos **originais**, com publicação e versão verificadas no momento da decisão.
2. **Um modelo de viés congelado**, com seus pesos e regras antes de gerar qualquer direção real.
3. Registrar cada previsão ou abstenção em recibo **separado**, com testemunha externa de horário antes da abertura, sem editar esta coorte.
4. Obter preços M15 da janela apropriada, confirmar fuso, bid/ask, origem e custos; só depois avaliar os acertos e perdas fora de amostra, explicitando taxa-base, amostra e abstenções.

**Status:** `validated_prediction_count=0`, `validated_accuracy=null`, `fx_bias=null`, `operational_bias=AGUARDAR`. Esta etapa congela a **população de pesquisa**, não eficácia preditiva.

**HARD NO-GO:** sem merge, deploy, Worker, Scheduler, feed pago, operação real, publicação do aplicativo ou alterações da interface da PR #1816.
