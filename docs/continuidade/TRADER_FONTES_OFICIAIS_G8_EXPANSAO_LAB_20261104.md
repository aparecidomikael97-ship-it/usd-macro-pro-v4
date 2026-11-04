# AtlasQuant Trader — fontes oficiais G8, cobertura documental ampliada (LAB)

**Checkpoint Mestre:** viés D1/W1/MN1 dos 28 pares das oito moedas, com
contexto macro, micro, geopolítico, notícias e calendário, mostrando por que
a moeda é forte/fraca **apenas quando isso estiver demonstrado**.

## Pesquisa de canais oficiais — 04/11/2026

Nove URLs abaixo foram encontradas como links diretos em páginas **oficiais
dos próprios publicadores**. São leads documentais, não feeds ao vivo já
integrados; um endereço RSS oficial tampouco comprova o valor econômico,
reação de preços ou direito de redistribuição.

| Moeda | Fonte | Assunto | Referência oficial |
|---|---|---|---|
| GBP | Bank of England, News RSS | Comunicados e notícias | [BoE RSS](https://www.bankofengland.co.uk/rss) |
| JPY | Bank of Japan, What's New RSS | Comunicados | [BoJ — uso do site](https://www.boj.or.jp/en/tips.htm) |
| JPY | Bank of Japan, Statistics RSS | Estatísticas | [BoJ — uso do site](https://www.boj.or.jp/en/tips.htm) |
| CHF | Swiss National Bank, Monetary policy RSS | Política monetária | [SNB — RSS/Calendário](https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds) |
| CHF | Swiss National Bank, Statistical publications RSS | Estatísticas | [SNB — RSS/Calendário](https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds) |
| AUD | Reserve Bank of Australia, Media RSS | Decisão de juros e comunicados | [RBA — RSS](https://www.rba.gov.au/rss/) |
| CAD | Bank of Canada, Press releases RSS | Política monetária e comunicados | [BoC — RSS](https://www.bankofcanada.ca/rss-feeds/) |
| CAD | Statistics Canada, Labour Atom | Emprego | [StatCan — feeds](https://www.statcan.gc.ca/en/sc/rss) |
| CAD | Statistics Canada, Prices Atom | Inflação | [StatCan — feeds](https://www.statcan.gc.ca/en/sc/rss) |

Os endereços exatos e domínios permitidos estão congelados em
`atlasquant_trader_g8_official_feed_registry_lab.py`. Eles são incluídos no
`SOURCES` do parser OFFLINE existente. As entradas originais USD (BLS, Fed)
e EUR (BCE) foram preservadas: 14 leads em sete moedas.

### Situação específica da Nova Zelândia

- Um endereço XML em domínio da própria RBNZ foi localizado:
  `https://www.rbnz.govt.nz/feeds/news`.
- Contudo, a página institucional pesquisada explica notícias e calendário,
  mas **não oferece o link RSS em seu texto examinado**. Portanto esse
  endereço permanece em `PENDING_LEADS` e não entra no parser.
- Páginas oficiais para consulta documental futura:
  [RBNZ notícias](https://www.rbnz.govt.nz/news-and-events/news),
  [RBNZ — política de divulgação](https://www.rbnz.govt.nz/news-and-events/how-we-release-information)
  e [Stats NZ — divulgações](https://www.stats.govt.nz/information-releases/).
- Isso **não significa** que NZD esteja sem notícias nem que seu viés seja
  determinável com dados apenas de outros países.

## Implementação protegida

`audit_g8_official_feed_leads_lab(at=...)` informa por moeda:

- leads cujo vínculo com o diretório oficial foi localizado;
- endpoints ainda pendentes;
- impossibilidade atual de atestar cobertura, publicação em tempo real,
  sinais, força cambial e causa de alta/baixa.

O leitor RSS processa apenas XML **sintético fornecido pelo chamador** para
as nove entradas adicionadas. Continua sem fazer HTTP, baixar RSS, salvar
payload, ativar cron, Worker, Render, AION ou enviar ordens. O contrato HTTP
condicional de laboratório passa a reconhecer as entradas admitidas porque
usa a mesma whitelist, mas **também não executa rede**.

## Antes de qualquer fonte ser usada de verdade

1. Validar payloads reais (RSS, RDF, Atom, datas, identificadores, links,
   304/ETag, redirecionamentos e limites de tamanho) com custódia e testes.
2. Conferir termos de uso, frequência, restrições comerciais, timezone,
   publicação revisada e risco de atraso nas divulgações.
3. Homologar o canal NZD ou projetar caminho oficial alternativo com
   evidência de fonte original.
4. Ligar os comunicados a números, consenso, expectativas de juros,
   cenários contraditórios e preços FX independentes em teste fora da
   amostra — sem confundir título de notícia com efeito de mercado.
5. Só então considerar coleta programada nas três janelas diárias gratuitas
   **planejadas**, nunca agora, e mediante aprovação específica.

**HARD NO-GO:** nenhuma contratação ou cobrança; três atualizações diárias
seguem não ativadas; PR #1803 DRAFT, sem deploy/merge. A menção a RSS não
promete notícias em tempo real nem preços negociáveis.
