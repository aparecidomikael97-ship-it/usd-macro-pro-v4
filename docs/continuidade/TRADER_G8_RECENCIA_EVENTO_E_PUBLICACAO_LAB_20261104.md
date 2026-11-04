# AtlasQuant Trader — recência dupla do evento e do documento (LAB)
Data: 04/11/2026 · PR #1803 / HARD NO-GO.

A auditoria de 16 fontes documentais tinha um risco: um comunicado
**publicado recentemente sobre um evento econômico antigo** poderia
ser marcado como documento recente e dar uma aparência de fundamento
atual. A data de publicação da página não é necessariamente a data
do acontecimento que se pretende explicar.

A classificação `RECENT_RELEASE_DOCUMENT_CLAIM_ONLY` exige agora
que **ambos** os campos declarados `event_at_utc` e `published_at_utc`
estejam nos últimos 90 dias em relação à emissão do relatório de
pesquisa. Um boletim reeditado hoje sobre inflação de seis meses atrás
continua antigo. A saída mostra ainda `newest_claimed_event_utc`.

O limite de 90 dias é triagem DOCUMENTAL interna, não regra oficial
nem garantia de que inflação, juros ou outros eventos sejam relevantes
para o Forex. Os dois horários continuam declarados pelo chamador;
não há autenticação da fonte, preço independente, prova de impacto
causal, consenso point-in-time ou capacidade de operar.

Três testes adicionados ao arquivo existente:
- evento antigo republicado: não se torna recente;
- evento realmente recente, ainda NÃO autenticado;
- documento velho não aumenta contagem de documentos recentes.

A PR segue em rascunho, com conflito de integração e sem CI
confirmada para este bloco. Sem merge, publicação, Worker, Render,
cron, cobrança nem ordens. D1/W1/MN1 permanecem AGUARDAR.
