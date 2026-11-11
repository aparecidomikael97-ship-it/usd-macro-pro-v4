# AtlasQuant Trader — ligação SEMÂNTICA CPI/G8 à matriz 28 FX e Precision Gate (11/11/2026)

**GO-LAB. PR #1851 em rascunho. Nenhum feed real, worker, assinatura, operação ou publicação de viés.** A integração foi testada usando documentos **sintéticos fornecidos pelo próprio repositório**. Resultado de teste do código NÃO é resultado de inflação real, autenticação independente de fontes ou acerto de previsão.

## Problema concreto que foi corrigido

A primeira integração `atlasquant_trader_fx_macro_precision_byte_join_lab.py` cruzava horários e hashes SHA256 das 16 fontes CPI/juros alegadas, mais o **Precision Gate com 6 verificações**, mas deixava explícito `economic_values_extracted_and_reconciled_to_body=false`. Era possível registrar, por exemplo, um valor de CPI inventado no recibo acompanhado de um arquivo qualquer e de seu hash autocoerente — a matriz e o gate continuariam sendo apenas documentais, sem detectar a falsidade do número.

Agora há uma **sétima etapa de pré-voo documental**, separada e conservadora, que reinterpreta o conteúdo CPI com os **leitores preexistentes para as 8 moedas**, em vez de inventar um parser duplicado:
- `atlasquant_trader_g8_cpi_semantic_byte_join_lab.py`
- `test_atlasquant_trader_g8_cpi_semantic_byte_join_lab.py`

O novo módulo **executa novamente** o join prévio das duas matrizes G8 D1/W1 + hashes + seis filtros Precision Gate e, para cada moeda, exige também:
1. Um único recibo `CPI_YOY` associado a bytes de CPI, hash SHA256 correto, horário e período explícitos.
2. Interpretação do arquivo **com o leitor específico** (EUR Eurostat JSON-stat HICP, USD BLS CPI-U NSA com derivação da taxa anual somente com denominador do mesmo mês do ano anterior; GBP ONS; JPY, CAD, NZD, AUD, CHF com leitores textuais já implementados).
3. **Coincidência exata do valor e do período** do recibo com a medida extraída/derivada do arquivo. Falha de período, erro de unidade/frequência, valor divergente, arquivo quebrado, vintages duplicadas ou fonte futura deixam `AGUARDAR`.
4. Moeda **NZD** recebe apenas CPI **trimestral**, nunca rotulada como “CPI mensal de setembro”. Estimativas preliminares de EUR mantêm flag de estimativa; não são representadas como valores finais.
5. Mantém sempre o **censo dos 28 pares**. Ausência de valor semântico em uma moeda afeta os **sete pares** que a contêm. Não preencher números ausentes com zero nem inferir 28 valores originais a partir de 2 moedas.
6. As métricas anuais CPI de regiões diferentes NÃO têm metodologia automaticamente idêntica. Mesmo com ambas as taxas locais checadas, `country_inflation_methodologies_harmonized=false`, `inflation_differential_allowed=false`; não somar/subtrair taxas com pretensão de força relativa tradável.

**Limitação honesta:** os testes usam fixtures, algumas contendo transcrições textuais sintéticas de páginas em vez da resposta bruta HTTP. Hash/local bytes e semântica consistente **não comprovam** assinatura do órgão emissor, primeira publicação, tempo de recepção, vintage histórica, correção de números transcritos, diferença econômica ajustada ou impacto cambial. O valor CPI coincidindo com os bytes fornecidos é *autoconsistência local do conteúdo*, não autenticação externa. **Não existem porcentagens de direção calibradas.**

## Testes integrados

Foram acrescentados **18 testes sintéticos** e incluídos no workflow Python 3.11/3.12. Cobrem:
- Reconciliação de GBP e USD na mesma observação mensal, sem gerar viés;
- Valor de GBP falso **apesar de SHA correto**;
- Período divergente; modificação de byte e hash inválido;
- Arquivo fabricado com hash novo correto, porém sem semântica de documento CPI;
- Denominador anual ausente no BLS: YoY = **indisponível**, nunca 0%;
- NZD trimestral vs mensal; HICP Eurostat estimado vs CPI-U americano;
- Cobertura sintética de **8 moedas e 28 pares** sem interpretar isso como oito fontes reais autenticadas;
- Falta de original, futura publicação/captura, NaN, duplicidade, estrutura inválida;
- Spread excessivo continua bloqueando via Precision Gate;
- Score 10/10 sintético nunca vira probabilidade nem sinal.

## Próximas etapas (P0) para transformar em conhecimento macro real

1. **Capturar e arquivar legalmente originais de cada emissor**, com URL final, status HTTP, hora UTC, hash dos bytes e vintage no momento da coleta. Não sobrescrever capturas antigas nem afirmar que downloads recentes eram conhecidos em datas passadas. Respeitar licenças de redistribuição.
2. **Vincular o extrator a cada formato oficial obtido na prática**: os leitores textuais para JPY, CAD, NZD, AUD e CHF precisam de revisão contra respostas brutas reais, não apenas exemplos transcritos. Falha de correspondência => AGUARDAR.
3. **Juros de política:** falta uma reconciliação semântica equivalente para as decisões oficiais das oito autoridades. O laboratório EUR/USD já diferencia **ECB DFR** de **Fed target range**, mas nível de taxas e anúncio de decisão têm significados diferentes. Não inferir automaticamente força cambial por subtração das taxas.
4. **Eventos com consenso point-in-time:** CPI/PPI e juros previstos vs divulgados, surpresa, revisões e regime. A expectativa do PPI dos EUA para 13/11 já foi congelada antecipadamente em duas publicações no AM12; verificações de 12/11 e 13/11 já agendadas, sem duplicá-las.
5. **Prova prospectiva A/B:** comparar macro básico vs Precision Gate completo no mesmo universo de oportunidades, preservando abstenções e custos. Só apresentar probabilidade após calibração fora da amostra.

## Condição operacional

Saídas da integração: `cpi_values_locally_reconciled_currencies`, `cpi_values_locally_reconciled_pairs`, razões de falha por moeda e por par; sempre `operational_bias=AGUARDAR`, `trade_authorized=false`, `can_feed_live_radar=false`, `calibrated_probability=null`.

**GO-LAB; NO-GO para integração ao Radar, IA sugerindo compra/venda ou comercialização como indicador validado; HARD NO-GO operação real.** Nenhum gasto novo.
