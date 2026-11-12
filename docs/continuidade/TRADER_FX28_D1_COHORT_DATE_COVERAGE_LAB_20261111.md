# AtlasQuant Trader — porta de cobertura D1 dos 28 pares (LAB, 11/11/2026)

## Motivo

O checkpoint AM12 de 07/11 preservou 84 séries (28 FX G8 × M15/D1/W1), 103.600 candles e 7 manifestos. A nova reauditoria local leu as 28 séries D1, verificou seus SHA-256 originais e 14.000 candles, comparando a presença da data **entre todos os pares**. A integridade local passou sem erros.

A investigação não inventou candles ausentes e reproduziu exatamente as cinco datas em dia útil com cobertura incompleta:

| Data | Pares D1 presentes | Descrição conservadora |
|---|---:|---|
| 2024-12-25 | 18/28 | Cobertura parcial, calendário não autenticado |
| 2025-01-01 | 8/28 | Cobertura parcial, calendário não autenticado |
| 2025-09-30 | 27/28 | GBP/NZD sem D1; 27 outros pares com barra |
| 2025-12-25 | 0/28 | Sem barras; não afirmar feriado certificado |
| 2026-01-01 | 0/28 | Sem barras; não afirmar feriado certificado |

Os 86 casos anteriormente classificados como possíveis calendários compartilhados permanecem apenas **candidatos à revisão**; o GBP/NZD de 30/09/2025 é uma **ausência isolada**, não um feriado presumido. A análise pressupõe presença de data D1 por UTC e não comprova sessões reais da corretora nem o corte de vela por servidor.

## Nova regra fail-closed

`atlasquant_fx_d1_shared_calendar_gate_lab.py` recebe a data, lista dos pares com candle D1 e coorte completa de 28 pares. Classifica:
- 28/28: somente completude documental da matriz; **não** libera trading.
- 27/28: ausência isolada; bloqueia ranking de 28 pares naquela data.
- 1–26/28: cobertura parcial; pendente de verificação do calendário.
- 0/28: nenhuma barra do conjunto; não cria data fictícia ou feriado certificado.
- Pairs duplicados, desconhecidos, coorte ou data inválida: bloqueio sem métricas.

**Em todos os casos:** `operational_bias=AGUARDAR`, `imputation_allowed=false`, `unrestricted_backtest_authorized=false`, `publishable=false`, `trade_authorized=false`, sem probabilidade calibrada nem assertividade alegada. A função é **estudo documental**: nenhum viés é emitido e não existe execução ou conexão de mercado.

## Evidência e limites

- Os hashes SHA-256 dos D1 são iguais aos valores salvos nos manifestos locais, mas manifesto e dados **não foram externamente atestados**; regravá-los juntos é possível.
- A observação de 28 datas não valida CPI/PPI, impacto macro ou causalidade. Não atesta Pepperstone, preço negociável nem condição futura do mercado.
- O MT5 do AM12 está acessível e possui especificações coerentes para 28 FX, mas a Observação do Mercado tinha **5 pares visíveis e 23 ocultos**, exigindo ajuste manual para futuras coletas uniformes. Nenhum símbolo foi habilitado automaticamente.
- Reanálise local e JSON de estudo mantidos no AM12 na pasta LAB. Dados CSV brutos permanecem fora do GitHub.
- Testes locais: nove verificações sintéticas aprovadas; a CI da PR executará os mesmos testes em Python 3.11 e 3.12.

## Caminho de integração

No futuro, antes de calcular ranking completo de força ou estimar assertividade D1, usar a porta com coorte obtida de `atlasquant_instrument_registry.FX_28`. Não tratar uma ausência como preço estável, feriado comprovado, acerto, erro ou `AGUARDAR` retrospectivamente escolhido.

Esta adição não realiza merge, deploy, publicação, comércio ou despesas.
