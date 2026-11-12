# AtlasQuant Trader — porta de rótulos de preço MT5 (LAB, 10/11/2026)

## Finalidade

Preparar a medição de resultado **após** a emissão de um viés, sem produzir viés,
treinar modelo ou dizer que houve acerto. A interface pura
`inspect_mt5_forward_label_lab(...)` recebe exclusivamente um registro do
manifesto AM12, os bytes de um CSV.gz já capturado e dois timestamps declarados
como abertura de barras. **Não lê o disco, MT5, internet, conta nem posições.**

## O que a porta verifica de forma local

1. O par precisa pertencer aos 28 cruzamentos G8 oficiais; timeframe apenas
   `M15`, `D1`, `W1` (sem converter W1 em M1). Símbolo, contagem de barras,
   início `bar_position_start=1`, nome do arquivo, erro de validação vazio e
   formato SHA-256 precisam corresponder ao registro do manifesto.
2. Limite de 1 MiB de arquivo comprimido, 2 MiB de CSV descomprimido; hash
   SHA-256 do CSV bruto deve coincidir com o registro. Isso demonstra somente
   autoconsistência entre arquivo e manifesto, não autenticidade da corretora.
3. Cabeçalho idêntico ao formato AM12, contagem exata de 3.000 barras M15,
   500 D1 ou 200 W1, valores OHLC positivos/finitos e coerentes, volumes e
   spread não negativos; timestamps crescentes sem duplicidade e intervalos
   inicial/final iguais aos declarados no manifesto.
4. Para calcular uma variação, entrada e saída devem corresponder a **duas
   linhas consecutivas** e sua diferença de aberturas deve ser exatamente
   900/86.400/604.800 segundos conforme timeframe. Se houver salto de sessão,
   fim de semana, feriado, horário do servidor ou lacuna, retorna bloqueio:
   **não estima, não preenche e não chama o salto de um candle comum**.
5. Se as verificações passam, apenas calcula `((close_saida / close_entrada)
   - 1) * 10.000`, em pontos-base, com indicação `UP/DOWN/FLAT` do preço
   observado — nunca da previsão do AtlasQuant.

## Saída e restrições

- Estado: `LAB_MT5_FORWARD_PRICE_LABEL_DOCUMENTARY_UNATTESTED` ou
  `LAB_MT5_FORWARD_PRICE_LABEL_BLOCKED` com motivo específico.
- **Sempre**: `operational_bias=AGUARDAR`, `trade_authorized=false`,
  `publishable=false`, `can_feed_validated_backtest=false`,
  `validated_accuracy=null`, `calibrated_probability=null`,
  `precommitted_prediction_present=false`.
- O campo `closed_bar_position_claim_only` deixa claro que a posição 1
  é uma **declaração do manifesto**; não é nova certificação da corretora.
- O CSV identifica a abertura da vela sob uma interpretação de epoch UTC.
  Isto **não** certifica o relógio, fechamento efetivo, timezone/sessão do
  servidor, independência da fonte ou disponibilidade histórica *point-in-time*.
- Um preço de fechamento observado mais tarde **não é** uma previsão feita
  antes desse fechamento. Falta associar exclusivamente sinais de viés com
  emissão prévia registrada e recursos macro disponíveis naquela data.
- A lacuna real isolada de **GBP/NZD D1 em 30/09/2025** permanece pendência.
  Um teste **sintético** de salto em GBP/NZD prova o bloqueio do código,
  sem reler ou corrigir a série real. Também se recusam intervalos de finais
  de semana/feriados, mesmo quando essas interrupções sejam legítimas.

## Validação desta rodada

- `test_atlasquant_trader_mt5_forward_label_gate_lab.py`: 13 testes com
  CSV.gz **inteiramente sintéticos** de formato AM12, incluindo 3 timeframes,
  preços UP/DOWN/FLAT, adulteração de hash, truncamento gzip, limite contra
  descompressão excessiva, gap nominal e não monotonicidade.
- Suíte local de regressão `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **235/235 PASS** em 10/11/2026.
- Nenhuma vela real AM12 foi fornecida ao executor nesta rodada. Os arquivos
  originais continuam somente na máquina autorizada; não houve rerun real do
  MT5, validação de mercado, taxa de acerto ou backtest estatístico.
- Sem alteração do terminal, conta, ordens, site publicado, workers, deploys,
  contratos ou cobrança. Não há conexão automática do módulo ao radar.

## Próxima barreira antes de medir assertividade

Fazer uma trilha imutável para cada **previsão emitida antes do evento**, com
versão do modelo, timestamp confiável, dados macro vintage corretos, duração e
regra de classificação do movimento. Só então confrontar previsões e preços
históricos com partição temporal OOS, embargo de rótulos sobrepostos, auditoria
de fontes e avaliação independente da correlação entre os 28 pares. Sem isso,
um rótulo documental não alimenta um número de assertividade publicável.
