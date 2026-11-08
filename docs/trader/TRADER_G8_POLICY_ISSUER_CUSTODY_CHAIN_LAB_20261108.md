# AtlasQuant Trader — próxima coleta de fontes de juros com cadeia local (LAB)

Pesquisa: **08/11/2026**. Aplicação somente em laboratório, sem coleta
automática ou uso operacional. O computador AM12 e os bytes originais da
divulgação **não** foram acessados nesta etapa.

## Valores de política monetária vistos hoje em sites dos emissores

Estes são valores **retrospectivos de páginas/documentos oficiais**, não uma
base de dados histórica ponto-no-tempo (P-I-T). Os instrumentos são diferentes:
um alvo em **intervalo** não equivale a uma taxa de depósito, e a diretriz
**aproximada** do Japão não equivale a uma taxa de mercado observada.

| Moeda | Divulgação | Instrumento exato | Valor descrito no documento |
| --- | --- | --- | --- |
| USD | 28/10/2026 | Faixa alvo de *federal funds* | **3,75%–4,00%**, não um único número |
| EUR | 29/10/2026 | Taxa de depósito do BCE | **2,50%** (outras taxas: 2,65% e 2,90%) |
| GBP | 05/11/2026 | *Bank Rate* do BoE | **4,00%** |
| CAD | 28/10/2026 | Meta da taxa *overnight* do BoC | **2,50%** |
| AUD | 03/11/2026 | Alvo da taxa à vista do RBA | **4,85%** (efeito indicado em 04/11) |
| JPY | 30/10/2026 | Diretriz para taxa interbancária *uncollateralized overnight call* | **em torno de 1,25%** |
| CHF | 24/09/2026 | *SNB policy rate* | **0,00%** |
| NZD | 28/10/2026 | *Official Cash Rate* do RBNZ | **2,75%** |

Documentos oficiais de decisão (URLs completas também constam em
`atlasquant_trader_g8_issuer_custody_chain_lab.py`):

- Fed: <https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm>
- BCE: <https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html>
- BoE: <https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026>
- BoC: <https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/>
- RBA: <https://www.rba.gov.au/media-releases/2026/mr-26-30.html>
- BoJ: <https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf>
- SNB: <https://www.snb.ch/en/publications/communication/press-releases-restricted/pre_20260924>
- RBNZ: <https://www.rbnz.govt.nz/news-and-events/news/2026/10/ocr-held-at-2-75-percent>

## O que ficou preparado para o próximo teste real no AM12

Implementado `atlasquant_trader_g8_issuer_custody_chain_lab.py`:

1. Aceita somente bytes de **um entre oito URLs de decisão previamente
   selecionados**, recebidos pelo chamador, sem efetuar qualquer GET próprio.
2. Cria envelope serializável com texto/PDF em **base64**, SHA-256 dos bytes,
   horário inicial/final **alegado pelo coletor**, MIME e identificador do evento.
   Limite de 1 MiB e janela de até 120 s; nenhum arquivo é gravado pela função.
3. Revê hash do corpo e hash do envelope, valida o instante da consulta e
   a ordem de múltiplas versões usando um encadeamento de hashes.
4. Recusa adulteração de corpo, URL, status, horário, fuso, ordem de versões,
   moedas misturadas e tentativa de atribuir uma consulta posterior a 28/10.
   Esta pesquisa só fica visível a partir de **09/11/2026 00:00 UTC**.
5. **Não certifica origem, entrega TLS, assinatura ou relógio independente**.
   Um agente malicioso conseguiria refazer hashes; somente um capturador
   confiável, carimbo de tempo e custódia externa poderiam elevar a prova.

## Restrições operacionais

- Os 8 níveis de juros são contexto **não normalizado**, sem subtração de taxas
  entre moedas, ranking de força, score ou probabilidade de direção.
- Os 28 pares D1/W1 permanecem `AGUARDAR`. Não é permitida junção a
  históricos M15 nem retroalimentação de sinais antigos.
- Os bytes de divulgação real, caso venham a ser capturados posteriormente,
  devem permanecer **localmente no AM12** até revisão de direitos de uso e
  cadeia de custódia; não publicar PDF/HTML integral no GitHub.
- Nenhum endereço de corretora, conta, preço, saldo, senha ou ordem é acessado.
- Sem Worker, deploy, agendamento, merge, assinatura paga ou novo custo.

## Próximo P0 de dados

No AM12, obter uma resposta oficial de teste **em primeiro plano** (sem
criar trabalho automático), preservando os bytes e o horário real de consulta.
Em seguida exigir autenticação da origem e carimbo de tempo independente para
que o registro possa algum dia ser considerado *primeira disponibilidade*.
Histórico reconstituído em 08/11 **nunca** é prova de disponibilidade em 2025
ou na manhã de uma decisão de outubro de 2026.

O problema de **GBPNZD D1 30/09/2025** e a ausência de um calendário
independente da corretora permanecem bloqueadores adicionais do backtest.
