# AtlasQuant Trader — três referências diárias G8 (02–04/11/2026) — LAB

Fontes oficiais consultadas:

- 02/11: https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261102/
- 03/11: https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261103/
- 04/11: https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261104/

A Banca d'Italia publica referências geradas no processo do Eurosistema/BCE, para informação. **Não** são cotações M15 de corretoras. Os valores foram **transcritos das páginas oficiais**, não obtidos como resposta HTTP original com bytes e SHA auditáveis. A data do registro não demonstra seu instante exato de disponibilização, nem verifica um vintage histórico.

Tabela — unidades de moeda cotada por 1 EUR:

| Moeda | 02/11 | 03/11 | 04/11 |
|---|---:|---:|---:|
| USD | 1.1216 | 1.1179 | 1.1267 |
| JPY | 177.10 | 176.95 | 178.30 |
| GBP | 0.83580 | 0.83358 | 0.83460 |
| CHF | 0.9193 | 0.9166 | 0.9188 |
| AUD | 1.6004 | 1.6007 | 1.6061 |
| CAD | 1.5673 | 1.5623 | 1.5701 |
| NZD | 1.9934 | 1.9876 | 1.9988 |

O módulo `atlasquant_trader_ecb_g8_three_day_reference_moves_lab.py` só calcula retrospectivamente os 28 cruzamentos usando `referência do euro para cotada / referência do euro para base` nos três dias. Para cada par retorna taxas indicativas derivadas, intervalos 02→03, 03→04 e 02→04 e sua variação percentual observada. São **84 variações históricas derivadas**, não 84 operações, previsões, sinais ou evidências independentes.

Sem ganho operacional declarado: não há valor de entrada/saída, spread, custos, dados de 15 minutos, consenso macro publicado antes do movimento, histórico point-in-time ou medição de acerto fora de amostra. O filtro de disponibilidade exige data de análise no mínimo 05/11 00:00 UTC, apenas limite conservador, NÃO comprovação de instante histórico de divulgação.

**HARD NO-GO:** D1/W1 = AGUARDAR, nenhum ranking de força de moeda, sinal, autorização de operação, Worker, scheduler, merge, deploy ou custo novo. Interface PR #1816 preservada. Próximo passo útil: captura de bytes originais e janela M15 com fonte autorizada, depois teste ex-ante medindo previsões registradas **antes** do movimento.
