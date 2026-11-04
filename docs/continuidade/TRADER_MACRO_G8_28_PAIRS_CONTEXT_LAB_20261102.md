# AtlasQuant Trader — Matriz macro G8 / 28 pares (LAB)
Data: 02/11/2026 · PR #1803 DRAFT · HARD NO-GO

## Papel desta entrega

O viés do Trader deve ser direto e verificável: **D1 primeiro,
W1 como confirmação e MN1 como contexto**. Esta etapa não produz
uma nova estratégia, sinal ou indicador de entrada. Ela organiza os
fundamentos conhecidos no momento do viés para permitir, depois,
estudos independentes sobre a contribuição da macroeconomia.

Foi implementado atlasquant_trader_g8_macro_context_lab.py, que
reaproveita atlasquant_trader_macro_surprise_pit_lab.py
(Anterior / Consenso / Atual com timestamps de divulgação e captura).

## Matriz de oito moedas

Cobre USD, EUR, GBP, JPY, CHF, CAD, AUD e NZD, com quatro grupos:
- **Inflação:** CPI, Core CPI, PCE, Core PCE ou PPI
- **Emprego:** NFP, ADP, desemprego ou salários
- **Política monetária:** taxa de juros de política
- **Atividade econômica:** PIB, PMI ou ISM

Até 32 eventos sintéticos por fotografia temporal. Nesta versão
restringimos a **um indicador pré-selecionado por moeda e grupo**
para impedir escolher o que acertou depois do fato. É um contrato
de pesquisa, não uma decisão sobre qual indicador será preferido
no produto final. Não presume que CPI/PCE/PMI de países distintos
possuem a mesma unidade, sazonalidade, relevância ou resposta de
mercado.

Cada campo apresenta o ID do evento, indicador, fonte, unidade,
leitura anterior, consenso, leitura realizada quando conhecida,
surpresa, horário de captura e situação:
- RELEASED_BEFORE_CUTOFF
- SCHEDULED_NOT_RELEASED
- STALE_RELEASE
- AUSENTE (campo nulo)

Uma regra artificial de no máximo **90 dias** foi usada apenas
para identificar informação desatualizada no LAB. Não atesta
recência suficiente para operar nem substitui o calendário real.

## Comparação par a par

Para cada um dos 28 pares canônicos e os quatro grupos, mostra
informação da moeda-base e da moeda-cotada e distingue:
- BOTH_RELEASED_FRESH
- UNRELEASED_EVENT_PENDING
- STALE_BILATERAL_CONTEXT
- INSUFFICIENT_BILATERAL_COVERAGE

Se os dois registros forem do MESMO indicador e mesma unidade,
mostra apenas SAME_RELEASE_RELATION ou
DIFFERENT_RELEASE_RELATION (acima, abaixo ou em linha com o
consenso). Em qualquer outro caso mostra NOT_COMPARABLE.

**Isso não é comparação de força macro ou de diferenças de
juros entre bancos centrais.** Uma surpresa inflacionária acima
do consenso não comprova apreciação da moeda: dependem do
que já era esperado, guidance, regime macro, curva de juros e
reação do preço. Nenhuma direção ou ranking macro é emitido.
O campo macro_strength_score é nulo. Nenhum veto é gerado
automaticamente.

## Limites de tempo e fonte

Somente valores SINTÉTICOS LAB são aceitos pelo adaptador de
surpresas já existente. Consenso precisa ter sido conhecido
antes da divulgação; leitura atual só pode aparecer após
divulgação e captura anteriores ao corte do viés. Agendas
futuras NÃO podem fornecer actual/surprise. O módulo rejeita
duplicações e conteúdo fora do contrato para impedir
seleção pós-resultado.

A saída inclui registros de evidência no contrato usado pelo
freeze_daily_bias_observation_lab.py, que pode congelá-los
junto de um lote de 84 previsões sintéticas. Esse hash local
continua SEM testemunha externa e SEM comprovação de que
dados históricos existiam no instante alegado.

## Testes e próximo estágio

test_atlasquant_trader_g8_macro_context_lab.py: **28 testes**
integrados ao CI Quality: universo de oito moedas / 28 pares,
matriz completa e esparsa, leitura conflitante, indicadores
distintos, unidades incompatíveis, disponibilidade e
horários, informação velha, eventos duplicados, ausência de
campos futuros, rejeições por dados malformados e integração
com o congelamento LAB D1.

Próximo estágio legítimo: decidir, antes dos resultados,
quais indicadores representarão cada grupo/país, qual a
regra de contexto (não pontuação arbitrária), obter dados
com horário e histórico de expectativas auditados, e
avaliar em testes fora da amostra se o contexto melhora
efetivamente a seleção de viés sobre a força de moedas.
Jamais somar indicadores correlacionados como votos
independentes sem estudo separado.

**Sem** chamadas a BCE/EODHD/Twelve Data, Worker, cron,
operações reais, gastos, merge ou deploy. PR DRAFT,
HARD NO-GO mantido e aplicativo publicado intocado.
