# AtlasQuant Trader — porta RSS BLS: identidade interna do item, sem ativação (LAB 03/11/2026)

**Estado: TESTES / LAB / HARD NO-GO.** Este contrato opera somente com bytes entregues por um chamador e não faz HTTP, não usa Render, não habilita notícias ao vivo e não emite direção, risco ou ordens.

## Problema específico corrigido

O auditor offline de latência anterior (`atlasquant_trader_official_news_latency_lab.py`) comparava SHA-256, dados de origem declarados e cinco horários. Um XML não relacionado à notícia poderia satisfazer o hash e ainda gerar intervalos aritméticos, **mesmo com a ressalva de que eram apenas alegações não atestadas**. A nova porta `atlasquant_trader_official_rss_item_lab.py` complementa esse auditor exigindo coerência **do item dentro do próprio conteúdo XML**.

Para o piloto restrito a BLS emprego 06/11 e CPI 10/11:

- Reutiliza integralmente o resultado do auditor anterior; se ele recusar fonte, identidade, digest, relógio futuro ou formato, a porta também recusa.
- Analisa apenas RSS **2.0** sintático usando `xml.etree.ElementTree` da biblioteca padrão, com limites de bytes herdados do auditor, máximo de 1.200 nós e 100 itens, e bloqueio explícito de DTD e entidades.
- Exige exatamente um `channel`, um `item` com link literal igual ao caminho informado pelo auditor, título de texto simples e `pubDate` em RFC 822 com fuso explícito; normaliza o horário declarado para UTC e o compara com o `feed_published_at_utc` do registro.
- Recusa links de itens duplicados, campos críticos ausentes ou aninhados, versão RSS diferente, relógio divergente ou corpo malformado.
- Devolve apenas o nome/título declarado e metadados de comparação. Não reproduz bytes originais, não interpreta texto para obter números de CPI/NFP, não infere consenso/surpresa, não recomenda trade.

**Atenção:** um atacante que controle simultaneamente XML, manifestos e relógios pode produzir um documento internamente consistente e falso. Mesmo com essa porta em estado aceitável, `source_origin_independently_attested=false`, `delivery_latency_independently_attested=false`, `realtime_news_enabled=false`, `can_feed_real_oos=false` e `trade_authorized=false`. O SHA-256 é só um teste de integridade local. Ainda faltam a obtenção real de bytes, revisão de licença e metadados autênticos, confiança de relógio, precisão e cobertura.

## Limites do piloto

- As únicas fontes relacionadas são `https://www.bls.gov/feed/empsit.rss` e `https://www.bls.gov/feed/cpi.rss`; catálogos oficiais: https://www.bls.gov/feed/ e https://www.bls.gov/help/hlp_rss.htm .
- O RSS disponível em produção pode diferir da fixture sintética ou da versão RSS 2.0 estrita exigida: **não declarar compatibilidade com um feed de verdade antes de testar com bytes capturados e conferidos**.
- A notícia sobre a divulgação e o valor econômico realizado são fatos diferentes; nenhuma leitura de CPI/NFP é extraída pelo código.
- Nenhuma medição real de atraso BLS/Fed, comparação com provedores pagos ou autorização de gasto foi realizada.

## Verificação

`python -m unittest -q test_atlasquant_trader_official_rss_item_lab.py`

24 testes locais com dependência simulada **somente no ambiente de desenvolvimento** passaram, incluindo RSS coerente, fuso -05:00, XML duplicado, XML com DTD/entidades, hora futura, corpo não relacionado, invalidação do SHA e bloqueio de produção. Os módulos/fixtures sintéticos auxiliares de desenvolvimento não foram enviados ao repositório. A bateria CI executa o teste sobre o auditor real do repositório e precisa ser conferida separadamente.

A próxima ação útil será verificar os bytes reais de um RSS oficial depois da divulgação, documentando metadados HTTP e a impossibilidade de comprovar recebimento histórico anterior somente com uma coleta retrospectiva. Para decidir se vale pagar notícias mais rápidas, é preciso medir várias divulgações com relógios e recibos independentes. Não basta um sucesso de parser.

**Sem custo adicional, Worker, scheduler, chave, coleta automatizada, serviço Render, ordem, merge, deploy ou mudança de interface.** PR #1803 continua DRAFT / HARD NO-GO.
