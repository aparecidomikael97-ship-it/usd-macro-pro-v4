# AtlasQuant Trader — PPI 13/11/2026: fechamento da cadeia de custódia do MT5 (LAB)

## Problema demonstrado

Até esta revisão, `inspect_ppi_one_event_study_lab` aceitava um `ClaimedLocalPriceArchive` que qualquer chamador podia construir diretamente com os 7 SHA-256 das séries M15. O relatório não exigia o manifesto `ppi_mt5_capture_manifest.json` que o capturador do MT5 já produzia com especificações dos símbolos. Isso podia contornar a validação de `name`, moedas-base/cotada, `digits`, `point`, período e status de segurança.

## Correção fail-closed

O relatório consolidado passa a:
1. Exigir o manifesto original na **mesma pasta** dos sete arquivos de preços.
2. Carregar o manifesto pela função `load_local_receipt_lab`, rejeitando ausência, symlink, conteúdo malformado, total de símbolos diferente de 7, candles por símbolo diferente de 17, hashes não hexadecimais, precisão dos símbolos inconsistentes, flags que falsamente afirmem dados autenticados, tentativas de alterar `AGUARDAR`, status de publicação, uso operacional ou timestamp anterior ao fechamento da janela.
3. Comparar exatamente o recibo obtido do manifesto com o recibo apresentado em `PpiStudyPacket`; não basta fornecer sete hashes válidos.
4. Executar, só depois disso, as verificações existentes de preços OHLC, horários, SHA-256 dos sete CSV, estudo de surpresa e amostras de spread.
5. Mostrar no resultado `local_mt5_capture_manifest_matched_unattested=true`, explicitamente mantendo `mt5_server_or_broker_independently_authenticated=false`. Nunca inferir precisão estatística, custos executáveis, sinais ou autorização de negociação.

O gate novo tem o estágio `MT5_CAPTURE_MANIFEST`; qualquer divergência retorna estado de bloqueio e `one_event_study=null`.

## Limitações não resolvidas

- SHA-256 local e manifesto local garantem apenas **consistência contra os recibos fornecidos**; alguém pode recriar dados, manifesto e hashes. É necessária âncora externa ou documentação independente do provedor, quando disponível.
- A fonte do histórico da Pepperstone não foi autenticada. O nome público `terminal_info.company` não é certificado de corretora nem de servidor de cotações.
- `spread` em candles M15 não equivale ao pico de bid/ask intrabar, nem a custos operacionais ou retorno líquido.
- Os preços do PPI de 13/11/2026 ainda são futuros em relação à preparação do estudo (11/11/2026). Os testes usam apenas HTML/valores/velas **sintéticos**, sem previsão real nem assertividade medida.
- Nenhuma chamada MT5, acesso a conta, ordem, agendamento, nova despesa, publicação, deploy ou merge foi autorizado por esta alteração.

## Testes

- `test_atlasquant_trader_ppi_one_event_study_join_lab.py`: faltou manifesto, SHA alterado, moeda cotada trocada, falso atestado da corretora, contagem errada, flags alteradas, tempo prematuro e symlink. O caso sintético íntegro ainda passa somente como análise documental `NO_GO`.
- `test_atlasquant_trader_ppi_mt5_m15_capture_lab.py`: carregador agora rejeita quantidades ausentes/booleanas, digests inválidos, status falsificados, horário sem timezone ou anterior à janela.
- Bateria existente de Python 3.11 e 3.12 na PR #1851; conclusão depende da CI.

**Política:** `operational_bias=AGUARDAR`, `publishable=false`, `trade_authorized=false`, `validated_accuracy=null`, `calibrated_probability=null`. A construção do AtlasQuant continua no LAB.
