# AtlasQuant Trader — ponte de hipóteses D1/W1 ↔ candles MT5 ↔ benchmark pareado (LAB)

**Estado em 09/11/2026 (UTC):** desenvolvimento local, somente leitura. O AM12 apareceu **Offline** no acesso remoto e não houve leitura dos **103.600 candles reais** nesta etapa. Os números de acerto nos testes são **inteiramente sintéticos**. Sem ordens, custos, merge, deploy, agendamento, alertas ou liberação do Radar.

## O problema resolvido

Já existiam dois componentes distintos:

- `atlasquant_trader_mt5_closedbar_outcome_lab.py`: reabre o `csv.gz` com hash de manifesto, confere OHLC, tempo de captura, existência da vela e a aresta nominal antes dela; extrai a direção documental da vela.
- `atlasquant_trader_regime_increment_benchmark_lab.py`: exige as mesmas oportunidades no baseline e na hipótese filtrada, três janelas separadas e contagens completas; só divulga taxas descritivas após amostragem mínima.

**Novo** `atlasquant_trader_mt5_paired_outcome_bridge_lab.py`: recebe hipóteses registradas por ativo e horizonte, IDs esperados, janelas declaradas e diretório dos snapshots. Valida IDs, timestamps, direção, sem misturar pares ou D1/W1. Para **cada** ID reabre a série compactada e chama o leitor existente, extrai `open/close`, `actual_observed_at` e SHA do CSV; monta os `DirectionalCase` para o benchmark.

Se **uma só vela estiver ausente**, hash incorreto, divergência temporal, target duplicado ou resultado não resolvido, devolve `LAB_PAIRED_OUTCOME_BRIDGE_BLOCKED` e `benchmark=None`. **Não calcula acerto com uma seleção dos 119 exemplos restantes quando o manifesto declarava 120.** Não preenche buracos, não inventa preço, não considera barra aberta.

Se as 120 forem resolvidas mas a amostra for pequena após filtro, o benchmark retorna `LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON`: contagens preservadas, **taxa de acerto suprimida**. Isso não é um erro nem autorização operacional.

## Limites que continuam explícitos

1. Hash SHA256 comprova consistência com um arquivo local, **não autentica a corretora**, histórico ponto-no-tempo, calendário, spread ou horário de negociação.
2. `prediction_locked_at`, `decided_at`, IDs, direção e `regime_veto` são **alegações do chamador**, não provas independentes de que a previsão existia antes do movimento. O mesmo vale para a lista completa de oportunidades e para as regras do filtro; precisam de testemunho externo prospectivo e auditoria.
3. Snapshots extraídos em novembro de 2026 contêm candles anteriores: o fato de existirem agora **não retrodata** decisões ou dados macro à época.
4. Um intervalo nominal ao redor do target não substitui a auditoria do calendário do broker. O caso GBP/NZD D1 de 30/09/2025 continua pendente, sem preenchimento ou exceção por presunção de feriado.
5. A direção por abertura/fechamento é **um rótulo de vela**, não retorno operacional, entrada, lucro líquido nem probabilidade calibrada.
6. Nenhum índice WIN/WDO/US500/NAS100/US30 usa esse contrato Forex; índices exigem dados e regras específicas.

## Resultado de teste reproduzível

No ambiente de testes local, os **arquivos exatos** dos dois módulos anteriores foram usados com o novo leitor. Somente o universo FX foi simulado por stub de teste correspondente à lista canônica de 28 pares; nenhum código stub foi enviado à PR.

```bash
PYTHONPATH=.:_testdeps:/mnt/data/atlasquant_mt5_outcome_lab:/mnt/data/atlasquant_regime_benchmark_lab \
  python -m unittest -q \
    test_atlasquant_trader_mt5_paired_outcome_bridge_lab \
    test_atlasquant_trader_mt5_closedbar_outcome_lab \
    test_atlasquant_trader_regime_increment_benchmark_lab
```

**70/70 testes sintéticos locais PASS:** 18 da nova ponte, 21 do leitor MT5 e 31 do benchmark anterior. Testados D1/W1 com 120 oportunidades fictícias e janelas separadas, ausência de 1 de 120 resultados, arquivo adulterado, timestamp futuro, target duplicado, risco de omissão, falta de amostra, abstenções e veto total.

**Cuidado:** o exemplo sintético que retorna **75% baseline / 100% filtrado** é propositalmente construído com preços artificiais. **Não citar esses números como desempenho do AtlasQuant.** O único objetivo desse caso é verificar a matemática e a contabilidade.

## Fila P0 para medição real

1. Quando AM12 ficar online, confirmar somente leitura dos hashes, manifestos e auditoria de calendário do arquivo original; **não repetir a coleta de 84 séries** sem necessidade.
2. Começar o registro **prospectivo** de oportunidades, com regras D1/W1 e veto fixados *antes* do fechamento, além de testemunho verificável externo ao banco local. Registrar também **AGUARDAR**.
3. Vincular as previsões reais aos candles pós-evento com a ponte; manter os rejeitados no denominador e separar ativos e horizontes.
4. Só depois fazer walk-forward temporal e comparar baseline vs filtros sem escolher retrospectivamente períodos favoráveis; custos e execução devem permanecer em análise separada.

**Estado operacional invariável:** `AGUARDAR`, `publishable=False`, `trade_authorized=False`, `validated_directional_accuracy=None`, `calibrated_direction_probability=None`, custo novo `R$0`.
