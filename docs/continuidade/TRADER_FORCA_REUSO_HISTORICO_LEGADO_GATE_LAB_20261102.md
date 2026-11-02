# AtlasQuant Trader — Auditoria dos candles legados para viés FX (LAB)

Data: 02/11/2026 · PR #1803 · HARD NO-GO.

## Descoberta concreta
O repositório contém o arquivo dados/autopilot_daily_cache_v107.json,
com horário de atualização geral informado de 17/09/2026, seis horas UTC.

Os dados foram examinados localmente na cópia de leitura do GitHub
(sem chamar fornecedor nem pagar por histórico). Evidências observáveis:

- Exatamente **7** pares com USD: EUR/USD, GBP/USD, AUD/USD,
  NZD/USD, USD/JPY, USD/CHF e USD/CAD.
- **320 candles D1 por par**, 2.240 registros no total.
- Intervalo dos timestamps: **22/10/2025 a 17/09/2026**, às
  00:00 UTC. Datas sincronizadas entre os sete pares.
- **83 registros com data de sábado ou domingo por par**;
  **581 ao todo**, sem prova de mapeamento da sessão ou
  fuso/fechamento de cada candle. Isso é um ALERTA, não
  prova automática de erro de preço: a origem pode usar
  convenção diferente de sessão.
- Faltam **21 pares independentes** do universo oficial
  dos 28 pares. Uma cotação derivada de triangulação
  NÃO se torna preço real e independente desses pares.
- O arquivo não comprova quem foi o fornecedor, licença
  de uso, carimbo imutável da disponibilidade histórica
  ou versão do preço disponível em cada instante.
- A última data do cache é antiga para o uso como
  **viés diário corrente em novembro de 2026**.

## Entrega técnica: gate de quarentena

atlasquant_trader_fx_legacy_cache_audit_lab.py faz auditoria
puramente local de estrutura, cobertura, ordem cronológica,
OHLC, horário com fuso, datas sincronizadas, fins de semana,
idade do último dado e metadados de atualização. Resultado:
QUARANTINED_UNVERIFIED_HISTORICAL_CACHE.

test_atlasquant_trader_fx_legacy_cache_audit_lab.py
inclui **15 testes**, sendo dois aplicados diretamente no
arquivo JSON existente, com contagem de datas e sessões.
A bateria faz parte do Quality CI e não faz HTTP.

Os gates historical_oos_ready, daily_bias_ready,
real_accuracy_publishable, trade_authorized, scheduler_enabled
e worker_enabled **nunca** são habilitados por esta auditoria,
mesmo que o arquivo acrescente metadados autodeclarados.

## Caminho para medir assertividade de verdade

1. Identificar fornecedor, direitos, unidade, fuso,
   dia da sessão e integridade dos candles já armazenados.
2. Obter ou autorizar séries históricas para a cobertura
   realmente necessária, sem pressupor que derivados são
   cotações independentes e sem comprometer orçamento.
3. Separar pesquisas de força G8 baseada em **sete pernas USD**
   (se a fonte for validada) da verificação com **28 pares
   independentes**. Rotular cada grau de cobertura.
4. Fixar carimbos de emissão antes do desfecho, dividir
   treino/teste por tempo, medir viés D1/W1/MN1 por par,
   comparando referências ingênuas e cenários neutros.
5. Exigir revisão independente antes de proclamar acerto
   real ou usar o viés no Radar de produção.

**Não fez:** cálculo do viés com histórico real, prova de
origem/licença, backtest real, API, deploy, Worker, agendador,
ordem, merge ou alteração do aplicativo publicado.
