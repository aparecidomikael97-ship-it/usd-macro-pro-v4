# AION — Knowledge Graph + Evaluation Lab

Data: 2026-09-25

## Checkpoint Mestre V12

O Checkpoint passa a persistir duas novas camadas:

- `knowledge_graph`;
- `evaluation_lab`.

Ambas possuem digest próprio e entram no relatório de integridade.

## Knowledge Graph

O grafo organiza conhecimento já registrado, sem criar fatos novos.

Tipos iniciais de nó incluem:

- LESSON;
- EPISODE;
- EXPERIMENT;
- VERSION;
- EVIDENCE;
- SCOPE;
- CAUSE;
- COMPONENT;
- POLICY;
- CONCEPT;
- RISK.

Relações incluem:

- SUPPORTED_BY;
- DERIVED_FROM;
- APPLIES_TO;
- CAUSED_BY;
- EVALUATES;
- DEPENDS_ON;
- CONTRADICTS;
- RELATED_TO;
- INVALIDATES;
- GOVERNED_BY.

### Regra de verdade

O grafo só deriva automaticamente relações estruturais que já estejam
explicitamente registradas em campos do Checkpoint, como:

- evidence_refs;
- source_episode_ids;
- applies_to;
- versões champion/challenger;
- causa de erro marcada como CONFIRMED.

Uma relação `CAUSED_BY` exige:

1. truth_state CONFIRMED;
2. evidência explícita.

Sem isso, o grafo não cria causalidade.

Contradição, dependência ou relação sem fonte explícita também não são
inferidas automaticamente.

## Sincronização

Escritas em Controlled Learning e Wisdom Journal atualizam os vínculos
estruturais do grafo no mesmo Checkpoint.

Também existe sincronização manual no Laboratório para reconstruir vínculos
explícitos já registrados.

## Evaluation Lab

Regras adicionais de evidência:

- baseline e candidate precisam ter resultado booleano em cada caso avaliado;
- cada caso precisa de referência de evidência;
- métricas comparativas exigem evidência geral da execução;
- um rótulo persistido como HUMAN_REVIEW_CANDIDATE nunca é confiado cegamente: o estado é recalculado a partir dos casos, métricas e evidências;
- falta de baseline, caso, métrica ou evidência resulta em NEED_MORE_EVIDENCE;
- nenhuma dessas avaliações promove ou publica uma versão.


O Evaluation Lab é o gate genérico de não-regressão do AION.

A suite padrão cobre inicialmente:

- verdade / não invenção;
- fronteira de autoridade;
- Guardian;
- integridade do Checkpoint;
- retomada durável;
- custo zero;
- mobile;
- orçamento de latência.

Métricas padrão incluem:

- task_success_pct;
- hallucination_rate_pct;
- safety_violation_count;
- critical_regression_count;
- p95_latency_ms;
- estimated_cost_usd_per_100_tasks.

## Estados

Uma avaliação pode ficar em:

- PLANNED;
- NEED_MORE_EVIDENCE;
- REJECTED_FOR_NOW;
- HUMAN_REVIEW_CANDIDATE.

Para alcançar `HUMAN_REVIEW_CANDIDATE`, a versão candidata precisa:

- ter casos avaliados com evidência;
- passar todos os casos críticos;
- não regredir métrica crítica;
- não reduzir a taxa geral de aprovação;
- mostrar pelo menos uma melhoria mensurável.

Mesmo assim:

- promoção automática = NÃO;
- mudança de produção = NÃO;
- deploy automático = NÃO;
- revisão humana = OBRIGATÓRIA.

## Interface

O Laboratório/Sandbox passa a exibir:

- tamanho e estado do Knowledge Graph;
- consulta de vizinhança de conhecimento;
- sincronização explícita;
- suites do Evaluation Lab;
- registro de avaliação baseline × candidate;
- reprocessamento de evidências já registradas.

Registrar uma avaliação vazia não gera resultado favorável: sem evidência,
o estado permanece `NEED_MORE_EVIDENCE`.

## Estado honesto

Este bloco implementa estrutura, persistência, avaliação e interface.

Não significa que:

- uma versão foi promovida;
- resultados de benchmark foram inventados;
- CI externo foi automaticamente convertido em evidência;
- relações sem fonte foram descobertas como fatos;
- qualquer regra de trading mudou;
- trading real foi habilitado.
