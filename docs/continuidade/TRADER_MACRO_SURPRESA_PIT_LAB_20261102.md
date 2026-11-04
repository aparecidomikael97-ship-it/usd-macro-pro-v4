# AtlasQuant Trader — Surpresa macro ponto-no-tempo (LAB)
Data: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO

## Objetivo de pesquisa
Para entender se macroeconomia melhora o viés diário dos **28 pares**,
o motor precisa separar rigorosamente:
1. **Anterior**: última leitura conhecida (vintage) antes do novo evento.
2. **Consenso**: expectativa do mercado fixada ANTES da divulgação.
3. **Atual**: resultado divulgado e realmente capturado ANTES da emissão
   do viés que pretende usá-lo.
4. **Surpresa**: atual - consenso, na mesma unidade, comparada com uma
   tolerância pré-declarada; acima/abaixo/em linha **não** determina
   automaticamente direção de moeda.

## Implementado
- Arquivo atlasquant_trader_macro_surprise_pit_lab.py: recebe duas
  estruturas explícitas e sintéticas, LAB_SYNTHETIC_MACRO_PRE e
  LAB_SYNTHETIC_MACRO_ACTUAL, mais horário da previsão e da auditoria.
- Valida 8 moedas G8 e indicadores CPI, Core CPI, PCE, Core PCE, PPI,
  NFP, ADP, desemprego, salários, juros, PIB, PMI e ISM. Não
  interpreta automaticamente o sinal macro nem prevê preço.
- Exige fonte, evento/indicador/unidade fixos, número finito,
  data/hora de captura do dado anterior e do consenso.
- Consenso precisa existir antes da publicação agendada e antes
  do viés; resultado precisa ter sido divulgado e capturado
  depois do consenso e antes da emissão. Horários sem fuso,
  dados futuros, campos extras e eventos com IDs distintos
  são recusados.
- Um resultado ausente enquanto a divulgação ainda é FUTURA
  vira apenas MACRO_SCHEDULE_ONLY, que não possui campo
  actual ou surprise. Se o resultado já deveria ter sido
  publicado, o motor não inventa um valor anterior/atual.
- Um resultado já capturado a tempo vira MACRO_ACTUAL_RELEASED
  com actual, consensus, previous, surprise, relação
  ABOVE_CONSENSUS/BELOW_CONSENSUS/IN_LINE_WITH_CONSENSUS.
- Não aceita fornecer uma surpresa futura e depois fingir
  que somente o calendário estava disponível: a estrutura
  com resultado indevido é recusada por inteiro.
- O campo market_impact_direction permanece UNDETERMINED
  até haver hipótese explícita de política monetária,
  expectativas e regimes, previamente registrada.
- A saída é diretamente compatível com o contrato
  freeze_daily_bias_observation_lab.py: o evento realizado
  pode servir de evidência para veto macro pré-registrado;
  um evento FUTURO não pode sustentar veto por resultado.

## Testes
test_atlasquant_trader_macro_surprise_pit_lab.py contém 26
testes: matemática de surpresa, limite de consenso, dados
parciais e adulterados, número não finito, fuso, publicação
fora da janela prevista, recepção depois da previsão,
múltiplos indicadores e integração real entre **módulos
de LAB** de pesquisa, congelamento e veto D1.

Os exemplos são INVENTADOS. Fonte não está autenticada;
nem a estrutura pre-release nem os timestamps possuem
custódia independente. Recalcular um snapshot sintético
não prova que ele existia no horário alegado.

## O que ainda falta para assertividade comprovada
1. Obter com autorização o calendário histórico de
   consensos e **vintages** anteriores, não somente
   resultados finais revisados.
2. Registrar fonte, instante de RECEBIMENTO e hash sob
   autoridade/custódia independente antes da previsão.
3. Fixar regra de interpretação de juros, inflação e
   emprego sem reutilizar resultados futuros.
4. Comparar baseline força, filtro macro e coberturas
   em OOS/walk-forward com spot auditado dos 28 pares.
5. Revisar a hipótese e os efeitos por moeda/regime,
   nunca atribuindo acerto ao sistema por testes inventados.

**LAB / HARD NO-GO**: não acessa EODHD/BCE/Twelve Data nem
outro fornecedor; não integra UI de produção; não compra
API, não faz merge, deploy, Worker, cron ou operações reais.
