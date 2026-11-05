# AtlasQuant Trader — Conciliação do XML BCE contra referências públicas (LAB)

Registro de 05/11/2026. Objetivo: identificar erros de transcrição das sete referências EUR para 02, 03 e 04 de novembro de 2026, antes de utilizar qualquer histórico em uma validação de mercado.

Fontes de contexto, que não são arquivos M15 nem cotações executáveis:
- XML histórico BCE (ainda não capturado neste ambiente): https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml
- Referências de página pública do Eurosistema publicadas pelo Banco da Itália: https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261102/ ; https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261103/ ; https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261104/

O leitor `atlasquant_trader_ecb_g8_xml_reference_history_lab.py` primeiro valida os bytes de XML entregues pelo chamador: estrutura, campos, datas, moedas, ausência de duplicidades, limites e horário de coleta declarado. Depois `atlasquant_trader_ecb_g8_xml_transcript_reconciliation_lab.py` verifica **21 células**, cada uma correspondendo a uma moeda e data. Um desacordo interrompe a conciliação; o relatório mostra os valores divergentes, sem substituição silenciosa.

Os cruzamentos correspondentes a 28 pares são **derivados** de referências da mesma família de dados. A conciliação dos 21 valores não significa que haja duas fontes de mercado independentes. As páginas do Banco da Itália divulgam referências do mesmo processo BCE/Eurosistema. Os arquivos de testes são sintéticos e se parecem com o XML, mas não representam download autenticado.

Mesmo numa conciliação aritmética perfeita: `original_xml_origin_authenticated=false`, `transcription_independently_authenticated=false`, `publication_instant_independently_witnessed=false`, `historical_vintage_point_in_time_verified=false`, `independent_broker_m15_prices_verified=false`, `historical_directional_accuracy_verified=false`, `fx_bias=null` e `operational_bias=AGUARDAR`. Um SHA-256 é apenas impressão digital dos bytes fornecidos, não prova de procedência.

Próximo requisito: obter e preservar bytes originais do BCE, origem e horário testemunhados, e um preço de mercado M15 com licença e características de bid/ask. Só então testar previsões D1/W1 criadas e registradas **antes** do período avaliado, preferencialmente em registro externo independente.

LAB/HARD NO-GO: não há merge, publicação, contratação, automação recorrente, Worker, Scheduler ou negociação. Não alterar PR #1816 da interface.