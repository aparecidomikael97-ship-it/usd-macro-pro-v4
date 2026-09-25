# AION — Data & Decision Fabric · Checkpoint V16

Data: 2026-09-25

## Posição na hierarquia

Este bloco implementa a prioridade técnica nº 4, depois de:

1. persistência runtime real;
2. soberania e resiliência;
3. confiabilidade de memória + Epistemic Core.

A próxima prioridade estrutural passa a ser observabilidade e autodiagnóstico.

## Objetivo

Dar a Trading, Investimentos, Studio, Negócios, Desenvolvimento e demais áreas
uma linguagem comum:

evidência → hipótese → teste → risco → decisão → resultado → aprendizado.

A Fabric é deliberadamente separada da camada de autorização. Evidência pode
sustentar uma decisão, mas nunca concede permissão de ferramenta.

## Evidence Envelope

Cada evento da Fabric registra, de forma compacta:

- domínio;
- tipo do evento;
- estado de verdade;
- fonte/proveniência;
- claim;
- digest do valor;
- resumo do valor;
- referências de evidência;
- tempo observado e validade;
- severidade;
- classe de privacidade;
- relação de supersessão.

CONFIRMED sem proveniência é rebaixado para UNKNOWN.

Dados classificados como SENSITIVE/SECRET não têm valor textual reproduzido na
Fabric; é preservado apenas o digest e o resumo fica redigido.

## Conflitos

Duas fontes independentes e confirmadas para o mesmo claim, com valores
diferentes, formam CONFLICT.

A Fabric:

- preserva ambas as evidências;
- não escolhe uma silenciosamente;
- não resolve conflito automaticamente;
- impede que uma decisão dependente seja promovida como pronta.

## Decision Case

Um caso de decisão contém:

- objetivo;
- hipótese;
- claims necessários;
- IDs de evidência;
- provas/testes;
- risco e impacto;
- reversibilidade;
- rollback;
- indicação de ação sensível.

Estados:

- DRAFT;
- RESEARCH_REQUIRED;
- TEST_REQUIRED;
- RISK_REVIEW;
- HUMAN_REVIEW_CANDIDATE;
- BLOCKED;
- CLOSED.

O maior estado de prontidão é HUMAN_REVIEW_CANDIDATE.

Isso NÃO significa autorização.

Sempre:

- action_authorized = false;
- automatic_execution = false;
- real_trading_enabled = false.

## Regra de alto risco

Decisão HIGH/CRITICAL ou sensível exige evidência CONFIRMED para os claims
necessários. Inferência/hipótese pode compor contexto, mas não é suficiente.

Quando aplicável, também exige:

- teste;
- rollback;
- ausência de conflito.

## Resultado e RCA

Um resultado pode ser registrado depois da decisão.

Resultado CONFIRMED exige evidência.

Causa-raiz CONFIRMED exige evidência própria.

Sem essa prova, a causa não pode ser inventada. Um resultado confirmado pode
ser marcado como candidato a aprendizado, mas não altera regra automaticamente.

## Integração transversal

A Fabric consegue derivar envelopes somente-leitura de estruturas já
persistidas no Checkpoint:

- tarefas operacionais;
- projetos do Studio;
- candidatos de Negócios;
- episódios de aprendizado encerrados;
- eventos Live Event Journal;
- Digital Twins.

Esses envelopes derivados não são gravados automaticamente de volta no
Checkpoint. Isso evita duplicar estado e mantém cada módulo como fonte de seu
registro original.

## Incrementalidade

Eventos têm IDs/digests e deduplicação determinística.

Mesmo ID com conteúdo divergente falha fechado.

Cache é apenas consultivo; nunca substitui a fonte canônica nem vira
autorização.

## Checkpoint V16

O Checkpoint passa a persistir:

`data_decision_fabric`

com:

- events;
- decisions;
- cursor;
- digest;
- política fail-closed.

A integridade do componente participa de `checkpoint_integrity_report`.

Um V15 sem a seção entra como MIGRATION_REQUIRED e é atualizado pelo fluxo
condicional de runtime já existente.

## Gateway

O Gateway local passa a:

- enxergar a postura da Fabric;
- expor conflitos;
- informar decisões em revisão humana;
- manter `executes_action=false`.

## Laboratório

O Admin/Laboratório mostra:

- eventos ativos;
- conflitos;
- casos de decisão;
- candidatos à revisão humana.

A primeira versão do painel é somente leitura.

## Provider

O prompt obrigatório passa a declarar:

- Data & Decision Fabric organiza evidência/hipótese/teste/risco/decisão;
- conflitos devem ser expostos;
- HUMAN_REVIEW_CANDIDATE nunca autoriza execução.

## Limites honestos desta etapa

V16 ainda NÃO é:

- um message broker externo;
- um stream distribuído;
- um conector automático de todas as fontes;
- um executor de ferramentas;
- um sistema de compra de mídia;
- um publicador automático;
- um deploy automático;
- um executor de ordens reais.

Ele é o contrato transversal seguro para essas áreas compartilharem evidência
e decisão de forma auditável.
