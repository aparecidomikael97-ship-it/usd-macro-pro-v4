# AtlasQuant Trader — leitor offline do XML original BCE para 28 cruzamentos G8 (LAB, 05/11/2026)

## Necessidade

A cobertura econômica G8 está pronta para teste; porém os 28 cruzamentos históricos de 02–04/11/2026 ainda foram derivados de taxas transcritas manualmente das páginas oficiais. Essas referências **não são preços negociáveis** e **não estabelecem previsão antes do movimento**.

Este incremento cria `atlasquant_trader_ecb_g8_xml_reference_history_lab.py`, preparado para receber **bytes fornecidos pelo chamador** do XML oficial BCE `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml`. Nenhuma chamada de rede acontece no módulo. A tentativa de baixar o arquivo diretamente neste ambiente não teve sucesso; **nenhum XML original real foi capturado ou autenticado nesta etapa**.

## Contrato de leitura e cálculo

Aceita um máximo de 400 KB de XML, exige namespace e remetente específicos do BCE, série diária em ordem cronológica decrescente, sem datas repetidas, sem fins de semana, sem DTD/entidades e sem taxas de câmbio duplicadas ou malformadas. Uma lista de 2–10 datas anteriores ao dia UTC declarado da captura é solicitada explicitamente; a ausência de qualquer uma é bloqueada, **sem preenchimento por aproximação**. Cada uma das datas solicitadas deve conter EUR como base implícita e USD, GBP, JPY, CHF, AUD, CAD e NZD.

Após validação **estrutural**, calcula as 28 referências cambiais derivadas usando `(unidades cotadas por EUR) / (unidades da moeda base por EUR)`, conservando precisão decimal. Também calcula apenas a variação **observada retrospectivamente** entre datas solicitadas consecutivas. Não é um cálculo de spread, retorno de execução, previsão ou moeda mais forte.

O SHA-256 registrado confere a integridade **dos bytes entregues ao leitor**, mas não demonstra que vieram realmente do BCE, que estavam publicados antes de um evento, nem que sua distribuição comercial está licenciada. Um arquivo construído artificialmente com a aparência do XML oficial também pode passar na validação estrutural. O campo `xml_bytes_original_http_origin_authenticated` permanece `false` mesmo quando o XML passa.

## Próxima prova real

Para avançar, capturar o **corpo HTTP original** com URL final, horário de coleta registrado pelo ambiente, identidade TLS/origem, hash SHA-256 externo e prova de disponibilidade histórica. Em paralelo, obter preços originais M15 de uma fonte autorizada, inclusive fuso, bid/ask e spread. O arquivo BCE obtido hoje não prova que determinado valor estava disponível na época analisada. Somente depois poderá ser avaliado o viés D1/W1 registrado **antes** do movimento e medido fora da amostra.

**HARD NO-GO:** nenhuma alteração nas telas da PR #1816; sem merge, deploy, Worker, scheduler, novos custos, moeda mais forte ou sinal negociável. D1/W1 e negociação permanecem em `AGUARDAR`. Testes usam XML sintético, não dados capturados.
