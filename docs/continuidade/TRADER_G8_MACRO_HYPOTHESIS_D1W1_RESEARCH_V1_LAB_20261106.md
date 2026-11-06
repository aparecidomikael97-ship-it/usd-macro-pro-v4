# AtlasQuant Trader — hipótese macro relativa G8/D1/W1 V1 (LAB, 06/11/2026)

## Por que esta etapa é diferente

Com o universo dos **28 pares Forex** e 56 avaliações prospectivas D1/W1 fixado previamente, agora existe a **primeira regra matemática explícita e reproduzível** que poderemos confrontar com dados oficiais futuros. Esta regra ainda é uma **hipótese experimental**, sem calibração, sem notícias ou preços ao vivo, **sem previsão real** e **sem resultado estatístico de assertividade**.

O código `atlasquant_trader_fx_g8_macro_hypothesis_lab.py` aceita exclusivamente **cenários declaradamente sintéticos**, nunca os promove a sinais e retorna `fx_bias=null`, `operational_bias=AGUARDAR`. Nenhum vínculo com o Radar, Painel Mestre, execução, agendamento ou conta MetaTrader foi criado.

## Método matemático V1 (pesos pré-fixados, não empiricamente validados)

Para **cada uma das oito moedas G8**, são necessários quatro componentes hipotéticos inteiros, de -2 a +2, **sem preenchimento automático de valores ausentes**:

| Grupo de pesquisa | Campo do simulador | Peso D1 | Peso W1 |
|---|---|---:|---:|
| Reprecificação de política monetária | `policy_repricing` | 40 | 45 |
| Efeito de inflação sobre expectativas de política | `inflation_repricing` | 25 | 20 |
| Surpresa de atividade econômica versus expectativa prévia | `growth_surprise` | 20 | 20 |
| Surpresa de emprego versus expectativa prévia | `labor_surprise` | 15 | 15 |
| **Total** | | **100** | **100** |

Para cada moeda, o **placar sintético de pesquisa** é a soma dos pesos multiplicados pelos quatro impulsos (-2 a +2). Para o par BASE/COTAÇÃO, o diferencial é `placar(BASE) - placar(COTAÇÃO)`. Isto garante coerência matemática entre os 28 cruzamentos e entre pares triangulares. Para diferenças absolutas de **até 40 pontos**, a hipótese fica indefinida; valores acima desse limiar apenas classificam a **relação entre placares sintéticos**, não a direção verdadeira do preço.

**Importante:** um CPI maior **não** significa automaticamente moeda mais forte. O sinal da variável `inflation_repricing` dependeria de uma reprecificação futura de juros versus consenso e do contexto monetário. Um número bruto de CPI ou taxa básica não pode ser inserido diretamente nesse campo. Os quatro impulsos ainda não têm adaptadores de dados reais, normalização por surpresa, regime ou volatilidade; somente o contrato matemático foi fixado.

**Não modelado ainda:** geopolítica, risco de aversão/safe haven, volatilidade, spread/custos, componentes microeconômicos completos, expectativas pré-divulgação assinadas e fontes independentes autenticadas. O modelo não pode ser considerado completo sem esses fatores. A política macro será testada **antes** de calibrar limiares/pesos; não ajustar pesos depois de observar resultados sem novo estudo fora de amostra.

## Regra de entrada experimental e bloqueios

O formato de entrada é `ATLASQUANT_TRADER_G8_SYNTHETIC_MACRO_FACTORS_V1` com `data_kind=SYNTHETIC_RESEARCH_ONLY`, horizonte D1 ou W1, horário UTC de **pesquisa autodeclarado** e exatamente oito moedas com quatro fatores cada. Recusa moeda/número ausente, fator extra, inversão de universo, valor fora de -2..2, inteiro booleano, duplicidade de campo JSON, tempo inválido ou tentativa de apresentar a fonte como `OFFICIAL_ECB` ou `LIVE_MARKET`.

Os **21 testes sintéticos** cobrem as duas matrizes de pesos, 28 pares, coerência triangular, zero diferencial, sensibilidade D1/W1, limiar neutro e recusas de insumos não válidos. Esses testes confirmam **cálculo e segurança**, não taxa de acerto em Forex.

**Próximo passo para uma hipótese operacional testável:** especificar os adaptadores de dados originais e respectivos horários de divulgação, calendário de consenso **prévio** e normalização quantitativa para os quatro fatores; congelar o protocolo, produzir entradas reais antes da janela e registrá-las em fonte externa com timestamp verificável; só depois medir a direção e os custos dos resultados, incluindo casos neutros, abstenções e dados insuficientes.

**HARD NO-GO:** somente LAB na PR #1815. Nada de merge, deploy, sinal real, Trader automático, execução de ordens, cobrança, acesso ao AM12 ou alteração da interface da PR #1816.
