# AtlasQuant Trader — XAU/USD: juros reais TIPS e separação prospectiva (LAB)

**09/11/2026. Escopo exclusivo de pesquisa; PR #1851 draft.** Não há sinal de ouro calculado, taxa de acerto, atualização publicada do Radar, execução, conexão ao MT5, captura HTTP nem custo adicional.

## Correção P0: não usar o resultado como entrada de previsão

O módulo de prioridade XAU/USD possuía oito domínios, incluindo `XAUUSD_PROSPECTIVE_OUTCOMES`, que é **um resultado posterior à previsão**. Exigi-lo como insumo anterior ao congelamento criaria confusão e risco metodológico de vazamento do futuro.

A correção mantém os oito domínios no plano geral, mas separa explicitamente:

- **Sete domínios pré-decisão**, que podem influenciar uma hipótese **somente se conhecidos antes da decisão**: dólar/DXY, juros reais americanos, Fed/expectativas, divulgações macro dos EUA, fluxos/demanda de ouro, geopolítica, preço e sessão do XAUUSD no broker.
- **Um domínio pós-alvo**, `XAUUSD_PROSPECTIVE_OUTCOMES`: serve para verificar uma previsão já registrada, jamais para produzir essa previsão.

`inspect_xauusd_evidence_lab` passa a aceitar apenas os sete pré-decisão. Uma tentativa de informar o resultado posterior é rejeitada. Mesmo todos os documentos aceitos são declarações não autenticadas; não produzem viés operacional.

## Adaptador de fonte oficial: Treasury 10-year nominal / TIPS real yields

Novo arquivo `atlasquant_trader_xauusd_us_treasury_yields_lab.py` lê, **offline e sem download**, dois arquivos CSV cujo formato esperado contém os campos `Date` e `10 Yr`:

1. Curva nominal de 10 anos do Tesouro americano — [Daily Treasury Par Yield Curve Rates](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve).
2. Curva real de 10 anos, títulos protegidos da inflação TIPS — [Daily Treasury Par Real Yield Curve Rates](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_real_yield_curve).

Documentação do emissor: [Interest Rate Statistics](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics).

O módulo recebe **bytes dos CSVs**, URL de página oficial informada pelo chamador, data/hora alegadas de publicação e captura, instante da consulta e instante de congelamento da hipótese. Ele:

- exige `publicação <= captura <= congelamento <= consulta`, com fuso e precisão de segundos;
- rejeita datas futuras, duplicadas, dados `N/A`/NaN, cabeçalhos inválidos, CSV excessivo, fontes trocadas, curvas com datas diferentes e valores além de faixa plausível;
- exige **duas observações comparáveis por curva** e data mais recente dentro de sete dias corridos do congelamento. Esse intervalo é um limite conservador de pesquisa, **não comprovação de feriados ou calendário**;
- calcula apenas o nível dos yields nominais e reais de 10 anos, a variação em **pontos percentuais** entre as duas datas e o spread nominal-real, que é um **proxy imperfeito** de breakeven de inflação (contém prêmios de risco/liquidez). Usa `Decimal`, evitando arredondamento silencioso;
- gera SHA-256 dos **bytes recebidos** para permitir comparação posterior. Hash e URL alegados **não autenticam** o emissor nem provam quando os dados foram capturados.

O retorno máximo é `LAB_XAUUSD_TREASURY_CONTEXT_DOCUMENTARY_UNATTESTED`, com `operational_bias=AGUARDAR`, `validated_accuracy=None`, `publishable=False`, `trade_authorized=False`. **Queda dos juros reais não se transforma automaticamente em COMPRA de ouro.** Falta cruzar Fed, dólar, CPI, NFP, geopolítica, sessão e preço do XAUUSD e realizar validação prospectiva específica para o metal.

## Testes realizados

- **38 testes unitários sintéticos locais**: 15 do módulo de prioridade após separar os domínios; 23 do adaptador Treasury com CSV de exemplo sintético, inclusive falsificação temporal, falta de ambas as curvas, discrepância de datas, valores inválidos e bloqueio de sinal.
- A rotina GitHub Actions D1/W1 deve incluir ambos os testes, em Python 3.11 e 3.12. Conferir execução após o commit; não presumir aprovação.
- O teste local do registro FX utilizou um stub de `_testdeps` **exclusivamente no ambiente local**, não enviado à PR. O workflow do GitHub deve usar o `atlasquant_instrument_registry.py` canônico.

## Fila de integração (sem contratar serviços)

1. Coletar e arquivar CSV oficiais reais com horário de captura e publicação **observado** (não fabricado), incluindo cabeçalho original, bytes e hash; estabelecer vínculo documental/autenticado com Treasury antes de alimentar o pré-voo.
2. Criar o adaptador real de preço XAUUSD e relógio D1/W1 a partir do broker quando AM12 estiver acessível; validar sufixo, spreads e sessões sem alterar o terminal.
3. Integrar fatores dólar/DXY, Fed, CPI, NFP, fluxo e geopolítica com freshness, veto de notícia e abstenção; nenhuma notícia isolada gera certeza de direção.
4. Fixar campanha do ouro prospectivamente, registrar vieses **antes** dos movimentos, preservar AGUARDAR e comparar os resultados com velas/horários comprovados; monitorar métricas exclusivas do ouro.

**Separação preservada:** Forex continua com 28 pares/56 posições D1/W1 por rodada; ouro segue `METAL:XAUUSD` independente. Sem merge, deploy, sinal, ordem ou cobrança.
