# AtlasQuant Trader — prova de captura pré-CPI (LAB)

**Pesquisa de 08/11/2026.** Preparação puramente local para a notícia mensal de
CPI dos EUA, prevista para **10/11/2026, 13h30 UTC**. Não houve acesso ao AM12,
ao site BLS ou a um provedor de pesquisa de consenso nesta implementação. Não
houve coleta real nem agendamento.

## Problema que esta etapa resolve

Uma fonte descoberta em novembro **não** prova que o mesmo arquivo já estava
disponível para um operador em outubro, nem que seu conteúdo é o original. Uma
URL, a hora escrita na página e até um SHA-256 consistente podem ser
fornecidos por alguém posteriormente. O backtest tem de distinguir:

| Campo | O que realmente demonstra |
| --- | --- |
| Publicação declarada | Alegação do emissor; não é um relógio independente |
| Captura declarada pelo coletor | Alegação local; não garante a hora real da primeira publicação |
| SHA-256 do corpo recebido | Identifica os mesmos bytes dentro do envelope; não autentica o autor |
| SHA-256 do envelope | Detecta alteração simples; não protege de um envelope inteiro refeito |
| Testemunha externa / documento original | **Ainda ausentes**; necessários para elevar a confiança |

## O que foi implementado

`atlasquant_trader_us_cpi_source_custody_lab.py` contém funções sem I/O para
receber bytes originais **passados pelo chamador** e criar envelopes. Admite
dois papéis estritamente separados:

1. **Valor anterior — setembro/2026:** somente o comunicado BLS de
   [14/10/2026](https://www.bls.gov/news.release/archives/cpi_10142026.htm),
   com referência de métrica *CPI-U cheio, variação mensal sazonalmente
   ajustada*. A publicação de 14/10 é uma **alegação do documento**, não
   prova de coleta histórica nesse dia.
2. **Consenso exato — outubro/2026:** documento de pesquisa dos analistas
   sobre o **mesmo** evento/métrica/unidade, com URL HTTPS declarada e hora
   de publicação anterior à notícia. Um nowcast de modelo não é aceito como
   essa pesquisa; o código não extrai nem confirma números da página.

O módulo confere a estrutura do envelope, a identidade declarada, o hash do
corpo, o hash do registro, o tamanho (até 1 MiB), a janela de captura de até
120 segundos, e os horários UTC sem fuso ambíguo. Uma captura anterior a
**09/11/2026 00h UTC** é recusada para esta pesquisa, impedindo que o código
crie recibos falsamente datados dos comunicados antigos. Uma captura concluída
após o instante da previsão também é recusada.

`inspect_us_cpi_pre_event_bundle_lab(...)` exige os **dois documentos**, mas
mesmo quando ambos passam no controle local retorna apenas:

`LAB_TWO_SOURCE_DOCUMENTARY_CANDIDATE_UNATTESTED`

Ele **nunca** retorna uma previsão, probabilidade, nota, viés ou ordem.
`ready_for_news_nowcast=False`, `ready_for_fx_bias=False`,
`historical_pit_eligible=False` e `operational_bias=AGUARDAR` são invariantes.

## O que ainda falta

- Um registro real, observado prospectivamente, da resposta BLS e do
  comunicado exato da pesquisa de consenso, incluindo autoria, horário de
  obtenção, conteúdo e permissão de uso. O módulo **não faz downloads**.
- Verificação independente da origem, do relógio de captura, das versões e
  da publicação. Uma captura feita em 09/11 pode ser examinada para uma
  previsão posterior do dia 09 ou 10; não torna a mesma fonte utilizável para
  simular uma previsão em setembro ou outubro.
- Extração e conferência humana dos números e das unidades; hoje uma página
  sintética qualquer pode passar pelo teste de integridade, **sem** virar
  fonte econômica confiável.
- Histórico suficiente e teste walk-forward P-I-T para comparar estimativa,
  consenso e valor anterior. Não existe precisão real demonstrada de 80% ou
  90%, e a probabilidade de surpresa não é a de acertar o EUR/USD ou o WIN.

## Testes

**20 testes sintéticos novos** da cadeia do CPI; no conjunto com o nowcast
`previous` (25), o pré-flight documental BLS (7) e a custódia de juros G8 (11),
**63/63 selecionados aprovados** em 08/11/2026. Não representa toda a suíte
legada, que possui dependências e artefatos indisponíveis no checkout.

Sem integração ao app, Radar, MT5, trading, worker, scheduler, deploy, merge
ou assinatura paga. Os bytes de fonte eventualmente capturados devem ficar
sob custódia local, não publicados no repositório.
