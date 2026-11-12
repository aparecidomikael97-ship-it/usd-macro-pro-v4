# AtlasQuant Trader — XAU/USD | integração documental Fed + CPI + NFP + juros reais (LAB)

**09/11/2026, somente laboratório.** O usuário está no celular e o AM12 continua offline. Nenhum candle real foi lido do MT5, nenhuma previsão real ou acurácia foi produzida, e não houve instalação, agendamento, operação, publicação ou cobrança. PR #1851 em rascunho.

## Objetivo

O projeto já tinha estudos e contratos individuais de Fed, CPI e emprego dos EUA, mais o leitor nominal/TIPS `atlasquant_trader_xauusd_us_treasury_yields_lab.py`. Faltava uma camada própria do ouro que exigisse essas evidências num mesmo congelamento de previsão, sem usar informação posterior ao movimento.

O novo `atlasquant_trader_xauusd_us_macro_release_join_lab.py` aceita **três documentos HTML originais alegados**, recebidos do chamador junto com URLs, SHA-256 de conteúdo, período de referência, publicação e captura alegadas:

- **FOMC_POLICY:** comunicado Fed com URL sob `www.federalreserve.gov/newsevents/pressreleases/monetaryAAAAMMDD*.htm`.
- **BLS_CPI:** release BLS arquivado em `www.bls.gov/news.release/archives/cpi_MMDDYYYY.htm`.
- **BLS_NFP:** release BLS arquivado em `www.bls.gov/news.release/archives/empsit_MMDDYYYY.htm`.

**Uma URL fornecida pelo chamador não prova que o emissor realmente publicou aquele conteúdo.** A rotina não faz HTTP, não autentica o produtor, não interpreta indicadores, não calcula surpresas em relação ao consenso e não confirma o horário de primeira divulgação. Páginas correntes mutáveis do BLS não valem como evidência histórica de arquivo.

## Regras de segurança

1. Exige três categorias distintas, sem ausência, repetição ou URL incompatível; o corpo deve ter conteúdo mínimo coerente com o tipo de documento.
2. Confere a ordem **divulgação alegada ≤ captura alegada ≤ congelamento da previsão ≤ inspeção**. A data codificada no URL deve concordar com a divulgação alegada e o período econômico não pode ser futuro.
3. Recusa documentos mais antigos que **150 dias para Fed** ou **65 dias para CPI/NFP**. São limites de triagem, não prova de que o documento é a última divulgação disponível.
4. **Reexecuta** o leitor de CSV Treasury nominal de 10 anos e TIPS real de 10 anos com os bytes recebidos, preservando a condição de mesma data e disponibilidade anterior à decisão.
5. Pode receber uma lista declarada de eventos FOMC, CPI e NFP. Se o congelamento estiver a até **40 minutos** de qualquer um, devolve bloqueio. A lista informada pelo chamador **não é um calendário verificado ou completo**.
6. Não gera compra, venda, probabilidade, nem confunde dados disponíveis depois do alvo com insumos da previsão.

Mesmo com todos os documentos coerentes, retorna somente `LAB_XAUUSD_US_MACRO_CONTEXT_DOCUMENTARY_NO_GO`. Sempre: `operational_bias=AGUARDAR`, `validated_directional_accuracy=None`, `publishable=False` e `trade_authorized=False`. **DXY e origem/licença de seus preços, cotação/spread/sessão XAUUSD no broker e validação prospectiva seguem pendentes.**

## Canais oficiais de referência

- [Federal Reserve: releases FOMC 2026](https://www.federalreserve.gov/newsevents/pressreleases/2026-press-fomc.htm).
- [BLS: releases CPI](https://www.bls.gov/cpi/news.htm).
- [BLS: arquivo Employment Situation](https://www.bls.gov/bls/news-release/empsit.htm).
- [Tesouro americano: curva nominal e TIPS real](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics).

**Nenhum número econômico real foi importado neste estágio.** Os testes usam documentos HTML e CSV sintéticos e versões de relógio escolhidas para regressão.

## Testes

Rodar com:

`python -m unittest -q test_atlasquant_trader_xauusd_priority_lab test_atlasquant_trader_xauusd_us_treasury_yields_lab test_atlasquant_trader_xauusd_us_macro_release_join_lab`

**60 testes locais sintéticos passaram** (22 novos, 38 anteriores). O teste do registro FX usa stub somente local; o GitHub utiliza o registro canônico. Confirmar execução remota no GitHub Actions Python 3.11 e 3.12 antes de reportar aprovação.

## Próximos passos

1. Capturar bytes verdadeiros das páginas oficiais, com fonte e primeiro horário de acesso **atestados** antes de cada previsão; validar a divulgação mais recente àquela decisão.
2. Adicionar dólar/DXY, política de licenciamento, preços e sessões XAUUSD da Pepperstone e veto de notícias com calendário real.
3. Congelar uma campanha **específica do ouro**, registrar previsões antes dos alvos e manter os AGUARDAR, acompanhando amostras fora do treino e custos reais.

Sem alteração dos **28 pares Forex/56 posições**, sem merge, deploy, negociação ou custo adicional.
