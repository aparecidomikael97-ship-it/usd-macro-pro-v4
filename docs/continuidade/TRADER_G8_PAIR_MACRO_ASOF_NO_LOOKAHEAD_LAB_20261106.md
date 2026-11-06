# AtlasQuant Trader — auditoria macroeconômica antes da previsão (LAB, 06/11/2026)

## Foco preservado

O AtlasQuant Trader precisa comparar as **duas moedas** de cada um dos 28 pares Forex antes de avaliar um viés D1/W1. A fase anterior capturou referências indicativas do BCE para sete moedas contra o euro e exportou uma amostra real de **116 barras EURUSD M15 de abril de 2026** pelo MT5. O histórico de abril não cobre a janela BCE de agosto–novembro e a conta demo do MT5 apresentou erro de autenticação. Não usar essas amostras incompatíveis para fabricar backtest.

Este incremento acrescenta `atlasquant_trader_g8_macro_asof_lab.py` e `test_atlasquant_trader_g8_macro_asof_lab.py`, sem depender do AM12. O contrato aceita um JSON de pesquisa contendo **um par canônico e o instante UTC da decisão**, mais recibos das publicações alegadamente conhecidas nesse momento.

## Entradas e salvaguardas

**Dois indicadores-piloto por moeda**, CPI anual (`CPI_YOY`) e taxa de política monetária (`POLICY_RATE`). Eles são apenas uma parte da futura leitura macro: emprego, atividade/PMI, surpresa versus consenso, Fed/BCE e geopolítica ainda terão regras próprias. Não é um modelo de peso econômico ou probabilidade de ganho.

Cada recibo exige: moeda, indicador, período de observação, valor numérico textual, instante UTC alegado de publicação, instante UTC alegado da captura, tipo de fonte e SHA-256 alegado. Regras de bloqueio:

- Rejeita informação com publicação ou captura declarada **posterior ao instante da decisão**, e captura anterior à publicação.
- Rejeita meses de observação posteriores ao mês da divulgação, moedas de fora do par, formatos inválidos, fontes não previstas e duplicação do mesmo indicador/período (revisão ambígua).
- Exige presença de ambos os indicadores em **ambas as moedas**; retorna falta/defasagem, sem preencher números ausentes.
- Limites de atualização piloto **CPI até 60 dias e política monetária até 120 dias** após publicação. Esses limites são **parâmetros conservadores de laboratório**, não atestados por órgãos oficiais, e não garantem atualidade econômica. A revisão futura pode exigir política monetária mais recente em decisões extraordinárias.
- O relatório omite os próprios valores numéricos não autenticados. Devolve apenas períodos, horários e alegações de fonte para uma revisão humana.

O controle está preparado para os 28 pares canônicos. Os **21 testes sintéticos** incluem os 28 pares, divulgação pós-decisão, captura pós-decisão, datas futuras, fontes espúrias, revisionamento ambíguo, indicador faltando/antigo, JSON inválido e invariantes sem sinal. Todos passaram no laboratório local com Python.

## Restrição crucial: prova estrutural não é prova histórica

O campo `published_at_utc` num JSON, sozinho, **não prova** que a publicação existia naquele instante; o mesmo vale para `captured_at_utc` e um SHA-256 autodeclarado. Mesmo um relatório `LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED` **não** permite construir viés nem validar uma previsão. A função sempre mantém:

`independent_release_time_attested=false`, `source_origin_authenticated=false`, `point_in_time_vintage_independently_verified=false`, `macro_values_verified_by_issuer=false`, `independent_broker_m15_prices_verified=false`, `validated_directional_accuracy=null`, `fx_bias=null`, `operational_bias=AGUARDAR`.

**Próxima prova real**: criar registros externos verificáveis no momento de cada divulgação, conferir revisão e valor diretamente no documento original, congelar a versão da lógica de viés **antes** do movimento e depois comparar com M15 de fonte e fuso verificados, em janelas D1/W1 com fechamento Nova York às 17h. Medir taxa de acerto apenas fora de amostra e informar também abstenções.

**HARD NO-GO mantido**: PR #1815 isolada; PR #1816 de interface intocada; sem merge, deploy, Worker/Scheduler, conexão à conta, operações ou novos custos.
