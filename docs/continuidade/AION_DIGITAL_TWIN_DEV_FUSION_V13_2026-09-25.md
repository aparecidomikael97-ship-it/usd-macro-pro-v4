# AION — Digital Twin + Dev Fusion + Release Confidence

Data: 2026-09-25

## Objetivo

Transformar a capacidade de desenvolvimento do AION em um pipeline auditável,
com simulação, revisão independente, tentativa de quebra, avaliação mensurável
e revisão humana antes de qualquer promoção.

## Checkpoint Mestre V13

O Checkpoint Mestre passa a persistir:

- `digital_twins`;
- `dev_fusion`;
- `release_confidence`.

Cada seção possui digest e participa da checagem de integridade.

## Digital Twin

O Digital Twin é um manifesto de simulação, não um ambiente de produção.

Registra:

- baseline;
- candidato;
- escopo;
- dependências;
- impactos esperados;
- rollback;
- observações;
- incerteza;
- evidências;
- bloqueios críticos.

Estados:

- PLANNED;
- EVIDENCE_INCOMPLETE;
- READY_FOR_EVALUATION;
- BLOCKED.

Uma observação sem evidência ou sem incerteza não torna o Twin pronto.
Bloqueio crítico força estado BLOCKED.

O módulo não edita código, não chama ferramentas, não faz deploy, não executa
rollback e não toca trading real.

## Dev Fusion Pipeline

Etapas:

1. PLAN;
2. BUILD;
3. REVIEW;
4. BREAK;
5. EVALUATE;
6. RELEASE_REVIEW.

Regras:

- Reviewer deve ser independente do Builder;
- Breaker/Red Team deve ser independente de Builder e Reviewer;
- estado terminal/revisão exige evidência;
- EVALUATE=PASS exige Evaluation Run ID;
- RELEASE_REVIEW não pode passar fora de ordem;
- achado crítico bloqueia o pipeline;
- PLAN, BUILD, REVIEW, BREAK e EVALUATE precisam passar antes de
  HUMAN_REVIEW_CANDIDATE;
- RELEASE_REVIEW=PASS somente encerra um pipeline que já chegou corretamente à
  revisão humana.

Mesmo DONE não executa merge/deploy. DONE significa apenas que o workflow
registrado terminou.

## Release Confidence

Release Confidence é **cobertura de evidência**, não probabilidade de sucesso.

Dimensões:

- DIGITAL_TWIN;
- DEV_FUSION;
- EVALUATION;
- QUALITY;
- RELEASE_GATE;
- ROLLBACK.

Estados:

- NEEDS_EVIDENCE;
- BLOCKED;
- HUMAN_REVIEW_READY.

O estado máximo não concede autorização.

Sempre:

- merge_allowed = false;
- deploy_allowed = false;
- automatic_promotion = false;
- requires_human_approval = true.

Um estado persistido é recalculado a partir das dimensões e evidências. Não é
possível confiar apenas em um rótulo salvo como HUMAN_REVIEW_READY.

## Integração com Evaluation Lab

O Dev Fusion usa o Evaluation Lab já existente. A etapa EVALUATE só pode passar
quando existe referência de run. O Release Confidence só considera a dimensão
EVALUATION confirmada quando o run associado está em HUMAN_REVIEW_CANDIDATE.

## Interface

A área Desenvolvimento passa a exibir:

- quantidade de Digital Twins;
- Twins prontos para avaliação;
- pipelines candidatos à revisão humana;
- Release Confidence;
- criação de Twin;
- registro de observação;
- criação de pipeline;
- registro de etapa;
- cálculo consultivo de cobertura de evidência.

A tela não oferece merge nem deploy.

## Estado honesto

Esta implementação NÃO significa:

- Codex/Cursor/Claude executando como agentes independentes em produção;
- sandbox de sistema operacional conectado;
- CI anexado automaticamente a todo pipeline;
- deploy automatizado;
- aprovação automática;
- rollback automatizado;
- trading real.

Ela cria o contrato seguro e persistente para integrar essas capacidades depois,
sem perder rastreabilidade, separação de funções ou aprovação humana.
