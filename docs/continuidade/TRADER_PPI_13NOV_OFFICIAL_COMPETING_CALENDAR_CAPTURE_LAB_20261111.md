# AtlasQuant Trader — primeira captura real de agendas oficiais concorrentes ao PPI (LAB)

**Momento da pesquisa e da captura:** noite de 11/11/2026 em Mato Grosso, madrugada de 12/11/2026 em UTC. **Evento principal:** PPI dos EUA de outubro/2026, **sexta, 13/11/2026 08h30 ET = 13h30 UTC = 09h30 MT**.

## Três agendas oficiais preservadas ANTES do evento

Através do computador autorizado **AM12**, foram realizadas leituras HTTPS públicas, uma por fonte. Os corpos HTML originais foram salvos no laboratório local, sem retransmiti-los ao GitHub. A captura local registrou o relógio do computador e os SHA-256 das páginas (valores imutáveis nesta revisão):

| Fonte oficial | Compromisso programado em 13/11 | ET / PT da fonte | UTC | Horário MT (UTC-4) | SHA-256 do HTML arquivado |
|---|---|---|---|---|---|
| EIA — Weekly Natural Gas Storage Report, calendário excepcional de Veterans Day | Estoque semanal de gás natural | 10:30 ET | 15:30 | 11h30 | `b54595ec6784c11c95ab448fa21d3f115b03a2bcc02960cab589fb0ad4cc1e04` |
| Federal Reserve Board, agenda de novembro | Discussão de Michelle Bowman sobre supervisão e regulação | 10:50 ET | 15:50 | 11h50 | `d5ebbecd6086b2d5a8f3958dc7b02a1903e9c3c69c6a9ad75103483a7bcf9383` |
| Federal Reserve Bank of San Francisco | Conversa de Mary Daly no evento de previsão econômica da UNLV | 09:00 PT = 12:00 ET | 17:00 | 13h00 | `fcb755bc8755d40bc802b77f4d00b9887b5548a87e372801b8f9f16c9d410ecb` |

**URLs oficiais correspondentes:**
- EIA: https://ir.eia.gov/ngs/schedule.html
- Federal Reserve Board: https://www.federalreserve.gov/newsevents/2026-November.htm
- Fed de São Francisco: https://www.frbsf.org/news-and-media/events/2026/11/conversation-mary-c-daly-unlv-2026-economic-forecast/
- BLS: https://www.bls.gov/schedule/2026/11_sched_list.htm

**Evidência do BLS:** a página oficial de agenda do PPI foi verificada por pesquisa web, mas o próprio download no AM12 retornou **HTTPError**. O manifesto declara `BLS_NOVEMBER.source_bytes_saved_locally=false` e **não inventa um hash** para a página inacessível. O evento PPI de 08h30 ET aparece também no calendário público oficial do BLS.

**Manifesto local:** `%LOCALAPPDATA%\AtlasQuant\LAB\PPI_20261113_OFFICIAL_CALENDAR_FROZEN_20261111\OFFICIAL_SCHEDULE_SOURCE_MANIFEST.json`.

Registro de captura do próprio AM12 em 12/11/2026 UTC:
- EIA 00:34:31.481798 — 8.105 bytes;
- Federal Reserve Board 00:34:31.925070 — 104.202 bytes;
- Fed de São Francisco 00:34:32.488940 — 126.269 bytes.

Os SHA-256 foram **recalculados depois da captura**, sobre os arquivos locais, e corresponderam integralmente aos três valores do manifesto. O horário é uma **alegação do relógio local**, não uma prova cronológica emitida por servidor de tempo independente.

## Impacto no protocolo das três janelas de PPI

- Referência pré-evento (13h15 a 13h30 UTC): **nenhum dos três eventos programados acima**.
- M15 (13h30–13h45 UTC): **nenhum dos três**.
- H1 (13h30–14h30 UTC): **nenhum dos três**.
- H4 (13h30–17h30 UTC): **os três** (EIA 15h30; Bowman 15h50; Daly 17h00 UTC).

A evidência mostra **outros eventos previstos na janela de quatro horas**; não demonstra que ocorreram pontualmente, que alteraram expectativas ou que afetaram efetivamente os preços do dólar. Uma agenda parcial jamais pode ser considerada livre de notícias, e **nenhum item estabelece causalidade**. Alguns pronunciamentos ou notícias inesperadas podem surgir fora desses registros.

## Alterações de código na PR rascunho

1. `atlasquant_trader_ppi_competing_calendar_lab.py` distingue agora `claims_complete_for_covered_period=false` de um documento inválido: aceita uma lista conhecida mas explicitamente **parcial**, sempre com revisão obrigatória e sem prova de ausência de outras notícias.
2. `atlasquant_trader_ppi_official_schedule_archive_lab.py` valida o manifesto, hashes imutáveis das três páginas, horários de captura anteriores à divulgação e trechos textuais oficiais que ligam a data ao horário. Exige origem de arquivo seguro, rejeita substituição, recusa afirmar que o BLS foi arquivado, e constrói `PreEventCalendarClaim` com cobertura **parcial**.
3. `atlasquant_trader_ppi_one_event_study_join_lab.py` aceita opcionalmente a pasta do arquivo oficial. Se ela for fornecida, deve revalidar as páginas originais e **não aceita** um calendário apresentado pelo chamador que discorde da evidência. Sem pasta, o estado continua documental/unknown, nunca limpo ou causal.
4. Testes sintéticos para ausência de arquivo, edição de HTML e digest, falsificação da captura, declaração indevida de completude, eventos nas janelas e conciliação com o relatório integral.

## Segurança e limitações

O módulo não faz downloads ao rodar nem envia ordens; o registro de fonte real foi capturado uma única vez no LAB. Os arquivos completos permanecem localmente no AM12. Testes do GitHub com HTMLs sintéticos validam a regra, **não os fatos do mercado**.

Sempre retornar `operational_bias=AGUARDAR`, `validated_accuracy=null`, `trade_authorized=false`, `publishable=false`, `causal_isolation_of_ppi_verified=false`.

**O foco permanece o viés seletivo e verificável dos 28 pares e índices, não sinais frequentes.** Este episódio serve para medir limites da evidência antes de qualquer estudo de assertividade.

## Reauditoria com os arquivos reais: precisão do timestamp

A primeira execução do leitor oficial contra o AM12 detectou `INVALID_INSPECTION_CLOCK` na porta de calendário. A rotina aceitava apenas timestamps sem parte fracionária, embora o manifesto de captura registrasse microssegundos (por exemplo, 00:34:32.488940 UTC). O problema não ocorria nas fixtures iniciais com segundos inteiros.

Correção: **captura e horário de inspeção podem ter microssegundos**; **horários agendados de eventos e limites de janela continuam estritamente em segundos inteiros**. Testes com relógio realista foram acrescentados ao parser do calendário e ao leitor de fontes. Nenhuma alteração nas três páginas preservadas, nos SHA-256, na raiz econômica ou na conclusão causal foi necessária. A verificação operacional com páginas reais é obrigatória antes de declarar esta revisão pronta.
