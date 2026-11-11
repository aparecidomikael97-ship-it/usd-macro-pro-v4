# AtlasQuant Trader — validação de identidade e precisão dos símbolos MT5 para o PPI (LAB, 11/11/2026)

## Lacuna corrigida

O capturador manual somente leitura do PPI em 13/11/2026 já exigia sete símbolos, 17 candles M15 fechados e integridade dos arquivos. Porém, `symbol_info()` era usado apenas para testar visibilidade. Isso permitia registrar metadados insuficientes para interpretar preços e spread, por exemplo um EURUSD cujo terminal expõe moeda-base ou moeda de cotação errada, ponto incorreto ou casas decimais inconsistentes.

A documentação oficial do MetaTrader 5 mostra que `symbol_info()` fornece `name`, `currency_base`, `currency_profit`, `digits` e `point`: https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py .

O capturador agora exige, para cada um dos sete símbolos canônicos:

- `name` exatamente igual ao solicitado (EURUSD etc., sem sufixo implícito);
- `currency_base` e `currency_profit` correspondentes às duas moedas do par;
- `digits` inteiro plausível para Forex (2 a 6), sem booleanos;
- `point` positivo, finito, e igual ao incremento descritivo `10 ** -digits` do próprio terminal.

Antes de gravar um CSV, todos os sete metadados devem passar. Se qualquer instrumento falhar, nada é salvo.

O manifesto local preserva, sem dados de conta, um registro **não atestado** desses campos e um nome público de empresa do terminal, quando seguro. O carregamento posterior do manifesto rejeita metadados ausentes, alterados ou que tenham sido rotulados falsamente como servidor ou broker verificado. Isso continua sendo uma verificação da consistência de campos fornecidos pelo terminal; o manifesto é local e pode ser recriado ou adulterado junto de seus hashes.

## Limites e proveniência

`terminal_info().company` descreve uma empresa associada ao programa instalado, **não prova qual servidor de cotações ou corretora forneceu os candles**. A captura *não* usa `account_info()`, login, servidor, nome de conta, posições, ordens, pedidos de mercado nem informações de conta. Não salva caminhos de instalação nem campos de configuração privada. Por isso:

- `active_quote_server_independently_verified=false`;
- `broker_identity_independently_authenticated=false`;
- `candle_utc_independently_authenticated=false`;
- `point_in_time_market_data_attested=false`;
- `operational_bias=AGUARDAR`, sem publicação, sinais ou operações.

O instrumento é observado no **momento da captura**, não há prova de que as especificações eram idênticas em todos os candles históricos. Para spread histórico negociável ainda será preciso fonte independente bid/ask, custos e servidor atestado; *não* usar `spread * point` como retorno líquido.

## Testes

Ampliação de `test_atlasquant_trader_ppi_mt5_m15_capture_lab.py` com regressões de base/cotação incorretas, nome diferente, `digits` inválido, `point` não finito ou incompatível, sanitização da empresa do terminal, proibição de dados de conta, manifesto adulterado e falsa atestação. Mantidos todos os cenários anteriores, inclusive array NumPy estruturado.

Execução exclusivamente sintética/offline nas duas versões Python do workflow da PR #1851. Sem MT5 real ligado nesta rodada, merge, deploy, gastos ou trading.
