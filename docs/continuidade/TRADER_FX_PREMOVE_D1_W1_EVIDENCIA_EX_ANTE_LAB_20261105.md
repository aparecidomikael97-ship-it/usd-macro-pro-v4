# AtlasQuant Trader — contrato para previsão antes do movimento (LAB, 05/11/2026)

Objetivo: sair de fotografias retrospectivas (BCE/Eurosistema dos dias 02–04/11) e preparar uma avaliação real de viés D1/W1 **sem olhar o futuro**.

O módulo `atlasquant_trader_fx_premove_lab.py` recebe separadamente dois JSONs UTF-8:

- Previsão: par canônico dos 28 Forex, horizonte `D1` (sessão entre dois fechamentos consecutivos às **17h de Nova York**, de domingo a sexta) ou `W1` (domingo 17h até sexta 17h de Nova York, cinco sessões), ambos com fuso IANA `America/New_York`, modelo LAB, direção `ALTA`, `BAIXA` ou `NEUTRO`, SHA-256 da evidência alegada, instante de corte da informação, instante alegado de criação, início e fim do período a avaliar.
- Resultado: mesmo par/período, identificador da fonte, SHA-256 alegado da fonte, dois preços textuais e horário de captura alegado **após** o encerramento do período.

O contrato de janelas usa `atlasquant_trader_fx_ny_rollover_lab.py`, não a meia-noite UTC, nem um deslocamento EST fixo. Em outubro/2026 o fechamento de 17h de Nova York é 21h UTC (EDT); depois da mudança do horário de verão em 01/11/2026, passa a 22h UTC (EST). O verificador recusa previsões iniciadas no sábado, janelas que atravessam o fim de semana como se fosse um pregão normal e uma semana formada por sete dias corridos. Esta convenção é apenas calendário de pesquisa: feriados, horários especiais e definição do broker ainda precisam ser atestados.

A auditoria rejeita entradas incompletas, objetos JSON com chaves duplicadas, preço ou fonte inválidos, futuro no corte dos dados, datas invertidas, horizonte diferente do declarado, troca do par ou resultado capturado cedo demais. Números são convertidos em `Decimal`; `NEUTRO` é abstenção, não uma operação vencedora. Retorna comparação aritmética apenas nos testes e marca permanentemente o caráter **não comprovado** dos registros.

**Alerta central:** SHA-256 prova somente a identidade dos bytes que o chamador forneceu. Qualquer pessoa pode criar hoje uma previsão com campo `created_at_utc` apontando para uma data passada. Isso NÃO prova que a previsão realmente existia naquele dia nem que seu algoritmo e evidências estavam disponíveis antes do movimento. Dados do BCE são preços de referência indicativos, não cotações negociáveis M15.

Portanto `forecast_precommit_independently_verified=false`, `historical_point_in_time_eligible=false`, `validated_prediction_count=0`, `validated_accuracy=null`, `fx_bias=null`, `operational_bias=AGUARDAR`. Uma coincidência aritmética não se torna taxa de assertividade nem performance de trade.

Para o primeiro backtest/forward test legítimo: produzir previsões ANTES do resultado, publicar e ancorar seus hashes e a versão do modelo em serviço externo com horário auditável, preservar dados macro de fato disponíveis no momento, capturar preços originais com origem e direitos de uso verificados, validar spread/custos e medir acerto fora de amostra, incluindo abstenções, taxa base e tamanho de amostra. Os três dias 02–04/11 não contam como previsões anteriores.

**HARD NO-GO:** LAB somente, sem Worker/Scheduler, operação, merge, deploy, assinatura paga, ranking de força; PR da interface #1816 intocada.