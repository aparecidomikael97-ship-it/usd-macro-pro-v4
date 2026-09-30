# AION BUSINESS Trend & Opportunity Intelligence V1

Schema: `ATLASQUANT_AION_BUSINESS_TREND_OPPORTUNITY_INTELLIGENCE_V1`

## Objetivo

Transformar a exigência de "buscar tendências o tempo todo e melhorar cada dia"
em um processo controlado, baseado em evidência e sem decisões automáticas
irreversíveis.

## Princípio

O ciclo oficial fica:

**Observar → Validar → Testar → Medir → Revisar → Promover somente com evidência.**

Buscar tendência não significa lançar qualquer novidade.

## Evidência

Toda evidência precisa conter:

- tipo de fonte;
- fonte identificável;
- segmento;
- afirmação observada;
- data/hora;
- confiança;
- estado de verdade;
- frescor.

Evidência velha, incompleta ou sem proveniência não confirma tendência.

## Score de oportunidade

O score combina, em modo controlado:

- sinal de demanda;
- intensidade do problema;
- aderência a receita recorrente;
- potencial de margem;
- aderência estratégica;
- complexidade de implantação;
- carga de suporte;
- qualidade/quantidade de evidência.

Estados:

- BLOCKED
- WATCH
- CANDIDATE
- STRONG_CANDIDATE

Mesmo um STRONG_CANDIDATE só pode seguir para experimento/revisão.

## Melhoria contínua

Mudanças são avaliadas com hipótese + métrica + antes/depois + tamanho da amostra.

Estados possíveis:

- INSUFFICIENT_EVIDENCE
- NO_CLEAR_IMPROVEMENT
- IMPROVEMENT_SUPPORTED
- REGRESSION_OBSERVED

`IMPROVEMENT_SUPPORTED` autoriza somente revisão humana futura.

## Monitoramento 24/7

O design declara `continuous_monitoring_desired=true`, mas o runtime atual
mantém `current_runtime_monitoring_enabled=false`.

O monitoramento real futuro dependerá de um coletor autorizado com proveniência,
limites, quotas e gates de runtime.

## Segurança

Nenhuma oportunidade:

- é lançada automaticamente;
- recebe gasto automático;
- vira publicação automática;
- gera contato automático com cliente;
- faz deploy automático;
- ativa runtime.

A versão atual é offline e avalia somente evidência fornecida.
