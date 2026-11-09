# AtlasQuant Trader — prova mínima do relógio MT5 D1/W1 (LAB)

**09/11/2026. Estado: código criado e testado localmente, sem ligação ao AM12.** O dispositivo remoto permanece **offline**. Não houve leitura de candles reais nesta etapa, nem previsão, negociação, merge, deploy, Worker, nova cobrança ou alteração dos gráficos. A PR #1851 continua rascunho.

## Objetivo concreto

A captura histórica de 07/11 possui séries D1/W1 com aberturas UTC documentadas em horários que **não correspondem ao padrão NY 17h** de referência. Isso **não prova erro do MT5, da corretora ou da conversão para UTC**, e não autoriza deslocar timestamps. É preciso confrontar a API em um instante conhecido, preservando as marcações originais.

O script `atlasquant_mt5_d1w1_minimal_clock_probe_lab.py` consulta só **EURUSD e GBPNZD**, cada um em **D1 e W1**, até **12 barras fechadas por série** por padrão (máximo 20), começando em `copy_rates_from_pos(..., 1, ...)`. Assim, são quatro séries e, por padrão, 48 marcações de tempo, em vez de repetir a coleta histórica dos 28 pares/84 séries/103.600 candles.

Ele usa somente os métodos `initialize`, `terminal_info`, `symbol_info`, `copy_rates_from_pos` e `shutdown`. **Nunca** chama `account_info`, `positions_get`, `orders_get`, `order_send`, `order_check`, `symbol_select`, login ou qualquer alteração de preferência do terminal. Exige símbolos já visíveis; se estiverem ocultos, interrompe em vez de habilitá-los.

## Verificações

- Captura o número epoch e a data UTC de cada abertura D1/W1; converte a hora para `America/New_York` com mudança de horário de verão correta.
- Compara como referência o padrão de **17h de Nova York** (D1 domingo a quinta; W1 domingo). Preserva cada timestamp bruto; nenhuma correção é aplicada.
- Exige séries completas, monotonicidade, barras nominalmente encerradas e relógio com fuso. Um resultado incompleto retorna bloqueado sem publicar ou calcular probabilidade.
- O JSON registra somente par/timeframe, horários, contagem, versão numérica do terminal, estado e hash local do relatório. Não salva preço, saldo, nome/ID de conta, login, senha, servidor ou histórico de ordens.
- `report_sha256_local_only` é apenas um checksum de conteúdo, **não uma prova de horário externo, corretora, integridade do broker ou vintage histórico**.

## Repetição no AM12 (apenas quando conectado e autorizado)

O Python 3.11 no AM12 havia usado `MetaTrader5` por uma instalação **isolada** em `%TEMP%\atlasquant_mt5_readonly_20261107`. Não reinstalar pacotes e não realizar coleta pesada. Antes de executar, confirmar que a pasta isolada e a biblioteca de fuso `tzdata`/IANA estão disponíveis. Se faltar algo, o código falha sem fornecer um falso atestado.

Exemplo PowerShell, com o arquivo do GitHub salvo localmente e terminal MT5 já aberto:

```powershell
$env:PYTHONPATH = "$env:TEMP\atlasquant_mt5_readonly_20261107"
py -3.11 .\atlasquant_mt5_d1w1_minimal_clock_probe_lab.py --count 12
```

Por padrão, imprime JSON e **não escreve arquivo**. Para registrar um relatório, passar `--report <caminho-novo>.json` em um diretório já existente. O script nunca sobrescreve um relatório. Nenhuma ação é executada automaticamente no computador offline.

## Resultado dos testes desta etapa

`python -m unittest -q test_atlasquant_mt5_d1w1_minimal_clock_probe_lab.py`

**13/13 testes locais com MT5 simulado passaram**. Eles verificam padrão NY 17h, transição de horário de verão, amostras com as divergências documentadas em novembro, terminal desconectado, séries faltantes, símbolo oculto, tempos repetidos, barra aberta, ausência de inicialização, exceções e ausência de operações de negociação. O ambiente sintético não prova o comportamento real do terminal.

## Portas de segurança remanescentes

1. AM12 online e MT5 disponível, sem pedir número de conta ou senha.
2. Leitura verdadeira e limitada das quatro séries, conferindo divergência de servidor e datadores em relação aos arquivos de 07/11.
3. Verificar independentemente qual fonte/server originou a série e a convenção de sessão, incluindo DST e feriados; sem inferir que match com NY17 autentica Pepperstone.
4. Corrigir **somente a metodologia de comparação** depois da prova. Nunca reescrever ou interpolar candles arquivados.
5. Congelar 56 posições futuras e registrar duas âncoras externas *antes* da abertura, com macro bilaterais e calendário verificados. Somente então avaliar resultados prospectivos.

**NO-GO:** publicação de vieses, acurácia real, automação, execução, orçamento adicional ou merge. `operational_bias=AGUARDAR`.
