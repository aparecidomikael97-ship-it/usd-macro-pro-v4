# AtlasQuant Trader — contrato M15 Forex 28/28 em LAB

Data: 04/11/2026. Escopo: laboratório offline, sem compras, sem brokers conectados, sem deploy.

## Objetivo

Preparar a inspeção de **candles de mercado M15** para os 28 pares G8 do
registro canônico. Esta trilha é independente das referências diárias do BCE.
As 21 referências sem EUR derivadas do BCE não contam como 21 observações
independentes de preços de mercado.

Implementação: `atlasquant_fx_m15_candle_lab.py`,
`analyze_m15_candle_export(payload, now=...)`. O módulo **não acessa redes,
corretoras, chaves, variáveis de ambiente, sistemas de ordens ou AION**.
Recebe apenas um objeto já fornecido pelo chamador em `OFFLINE_RESEARCH`.

Adaptador adicional `atlasquant_oanda_m15_export_lab.py`,
`analyze_oanda_m15_export(responses, captured_at=..., now=...)`:
- Recebe **28 respostas já fornecidas** no formato v20 de candles por instrumento
  (`instrument`, `granularity`, `candles`). Não cria sessões nem faz GET.
- Exige os símbolos na orientação canônica (`EUR_USD`, etc.) e rejeita
  duplicidade, falta de instrumento, período diferente de M15 ou bid/ask ausentes.
- Seleciona as duas últimas velas fechadas; descarta no máximo um candle ainda
  aberto quando ele vier no final da resposta, sem fingir que está fechado.
- Rejeita campos de credenciais e remove volume, ponto médio e quaisquer campos
  extras antes de delegar à validação M15. Nenhum dado bruto é publicado.
- A origem é identificada permanentemente como
  `OANDA_V20_FORMAT_UNVERIFIED_OFFLINE`; mesmo quando a estrutura passa,
  `provider_authenticated` e `publishable` continuam falsos.

## Contrato de entrada

- `schema=ATLASQUANT_FX_28_M15_CANDLE_IMPORT_LAB_V1`
- `state=OFFLINE_RESEARCH`, `kind=MARKET_CANDLE_EXPORT`
- `source_claim` de texto (declaração, **não autenticação**)
- `captured_at` com timezone; idade máxima de 5 minutos frente ao relógio
  informado, apenas para o ensaio de frescor
- Exatamente 28 chaves de pares canônicos (`EUR/USD`, etc.)
- Por par: `source_claim` igual ao da coleção, `granularity=M15` e
  **exatamente dois candles completos consecutivos**, os dois últimos fechados
- Cada candle: `time` com fuso, alinhado ao início de 15 minutos; `complete=true`;
  OHLC numéricos positivos `o,h,l,c` tanto em `bid` quanto `ask`

Validações atômicas: 28/28 ou bloqueia tudo; horários M15 iguais em todos os
pares; sem candle futuro, incompleto, fora de ordem ou muito antigo; OHLC
internamente consistente; bid-close menor ou igual a ask-close; spread
percentual máximo de 0,75%; variação de dois fechamentos M15 limitada a 15%;
resíduo máximo entre os retornos dos cruzamentos G8 de 0,30 p.p. logarítmico.
Os limites são **guardas experimentais**; não foram calibrados para negociação.

Uma falha produz `state=BLOCKED` e rankings vazios. Um conjunto
estruturalmente válido produz `RESEARCH_ONLY` com variação M15 e diferença
relativa entre moedas, mas preserva:

- `provider_authenticated=false`
- `independent_observations_verified=false`
- `accuracy_verified=false`
- `has_executable_bid_ask=false`
- `publishable=false` e `trade_authorized=false`

Os bid/ask do candle são **históricos**, não uma oferta executável no instante
de consulta. Coerência algébrica não comprova autenticidade, preços reais,
liquidez, rentabilidade ou independência das observações fornecidas.

## Fonte de mercado — avaliação pendente

OANDA fxTrade Practice é candidata para teste privado, condicionada à
disponibilidade regional, adesão às condições de uso, autenticação adequada,
confirmação de 28/28 instrumentos e dos campos de bid/ask/M15. Nenhuma conta
ou token foi solicitado ou utilizado neste bloco.

Referências do fornecedor:
- https://developer.oanda.com/rest-live-v20/development-guide/
- https://developer.oanda.com/rest-live-v20/instrument-df/
- https://developer.oanda.com/rest-live-v20/pricing-ep/

Quando houver autorização e conta disponível, o adaptador de rede deverá ser
separado deste validador, obter **somente GET** de instrumentos e candles,
descartar o candle ainda aberto, normalizar timestamps para UTC e guardar
segredos fora de payloads e logs. Antes de exibir preços no Radar, verificar
licença para uso na interface, cobertura, cotações atuais, spread e latência
observados; exigir gate de proveniência independente. O simples preenchimento
do contrato LAB nunca promoverá dados a `VALIDATED_DAILY`.

## Testes e restrições

Fixtures **sintéticas** exercitam orientação, 28 pares, candles completos,
datas, sincronização, spread, OHLC, inconsistência e recusa de credenciais
no payload. O Radar publicado, AION, Worker, Render e execução real não mudam.
Nenhum teste sintético justifica alegação de precisão operacional.
