# AtlasQuant Trader — fontes oficiais RSS, janela PIT e revisões (LAB)

**Vínculo com o Checkpoint Mestre:** P1 itens 1/4/5 (macro, notícias,
calendário) e P2 (três atualizações completas por dia, sem cobrança). Não
altera as prioridades de força relativa, viés D1/W1/MN1, micro/geopolítica
nem a proibição de sinal operacional antes de custódia/OOS.

## O que foi implementado

`atlasquant_trader_official_rss_capture_lab.py` normaliza **bytes RSS/Atom
fornecidos pelo chamador**, com leitura limitada a 256 KiB e até 100 itens.
Os cinco leads oficialmente documentados são:

| Fonte documental oficial | Moeda | Tema | Feed |
|---|---|---|---|
| BLS Employment Situation | USD | Emprego | [BLS](https://www.bls.gov/feed/empsit.rss) |
| BLS CPI | USD | Inflação | [BLS](https://www.bls.gov/feed/cpi.rss) |
| Federal Reserve Monetary Policy | USD | Política monetária | [Fed](https://www.federalreserve.gov/feeds/press_monetary.xml) |
| BCE Press | EUR | Comunicados | [BCE](https://www.ecb.europa.eu/rss/press.html) |
| BCE Statistical Press | EUR | Estatísticas | [BCE](https://www.ecb.europa.eu/rss/statpress.html) |

O leitor verifica a sintaxe, exige timestamp com fuso, URL de artigo em
host oficial correspondente ao canal e identificador estável. Guarda
apenas **hash diagnóstico do payload fornecido**, título, URL e hora da
captura declarada; não arquiva bytes originais nem atesta TLS/origem.
Conteúdo DTD/ENTITY, dados grandes, URL falsa, timestamp futuro inesperado
e duplicação de identificador são recusados.

O comparador `diff_official_rss_captures_lab` marca:

- Artigo novo (identificador desconhecido na captura anterior).
- Revisão (mesmo identificador com conteúdo diferente).
- Desaparecimento de uma lista parcial como **não confirmado**, nunca
  como exclusão, retratação ou notícia desmentida.
- Moeda relacionada e até sete pares com **possível contexto**, sem afirmar
  que o evento muda o preço ou autoriza operação.

## Limites e continuidade

**Não foi ativada nenhuma coleta externa.** Os testes usam XML sintético;
nenhum RSS real foi baixado nem o atraso de publicação/recebimento medido.
Os URLs vêm das páginas oficiais de RSS do [BLS](https://www.bls.gov/feed/),
[Federal Reserve](https://www.federalreserve.gov/feeds/feeds.htm) e
[BCE](https://www.ecb.europa.eu/home/html/rss.en.html), mas precisam de
verificação operacional, tratamento de redirecionamentos, cache condicional,
termos comerciais e versões originais antes de implementação em servidor.

Só USD e EUR têm leads deste piloto. **GBP, JPY, CHF, AUD, CAD e NZD ficam
pendentes** para canais próprios; nenhum deles é declarado sem notícias.
Esses RSS também não são fontes completas de geopolítica ou dados negociáveis.

O sistema deve manter o modo atual de **três revisões diárias**; não abrir
checagens extras nem contratar serviço de uma hora sem autorização explícita.
Próximo bloco: coletores por fonte com tempo limite, ETag/Last-Modified,
armazenamento e trilha de alterações confiável, todos com preflight isolado
antes de ativar qualquer cron. As notícias entrarão no dossiê causal apenas
como fatos de origem/custódia demonstrada, com contraprovas e atraso exibidos.

## Testes e governança

```sh
python -m unittest -q \
  test_atlasquant_trader_official_rss_capture_lab.py \
  test_atlasquant_trader_g8_context_completeness_3x_lab.py \
  test_atlasquant_trader_monitoring_cadence_lab.py \
  test_atlasquant_trader_official_change_detection_lab.py
```

LAB apenas. PR #1803 DRAFT/HARD NO-GO; sem Render, AION Worker, cobranças,
ordens, novos dados reais ou alteração do aplicativo publicado.
