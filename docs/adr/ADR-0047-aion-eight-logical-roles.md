# ADR-0047 — AION usa oito papéis lógicos sob um único núcleo

Título: AION usa oito papéis lógicos sob um único núcleo  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

O ecossistema precisa combinar execução, estratégia, segurança, memória,
controle de custos, confiabilidade e crescimento comercial sem multiplicar
custos de modelos independentes.

## Problema

Criar várias IAs completas e autônomas aumenta custo, risco de conflito,
duplicação de memória e possibilidade de permissões inconsistentes.

## Alternativas consideradas

1. Uma única IA monolítica sem papéis especializados.
2. Oito IAs independentes e permanentes.
3. Um AION central com oito papéis lógicos especializados e ativação sob demanda.

## Decisão

Adotar a alternativa 3.

Papéis:
1. AION Núcleo / Orquestrador.
2. Arquiteto / Estrategista.
3. Guardião / Auditor.
4. Executor / Operador.
5. Memória / Conhecimento.
6. FinOps.
7. Observabilidade / Confiabilidade.
8. Sucesso do Cliente / Comercial.

Os papéis podem compartilhar modelos, memória autorizada e infraestrutura.
Nenhum papel especializado recebe autorização implícita para ação crítica.

## Consequências

O sistema ganha especialização sem exigir oito modelos caros em execução
contínua. O roteamento deve escolher o papel e o modelo adequados conforme a
tarefa, custo, risco e contexto.

## Componentes afetados

- AION Core;
- roteador de especialistas;
- memória;
- Guardian;
- Executor;
- FinOps;
- observabilidade;
- Business / Customer Success.

## Segurança

A autoridade de cada papel continua limitada por RBAC, tenant, contexto e gates
humanos. Arquiteto e Auditor não executam mudanças críticas. Executor não pode
elevar sua própria permissão.

## Compatibilidade

Compatível com a decisão anterior de núcleo central único. Os oito papéis são
funções internas, não substituem os especialistas de domínio já existentes.

## Rollback/migração

A introdução deve ser gradual e por feature flags. Enquanto um papel não estiver
implementado e validado, o núcleo mantém o comportamento anterior fail-closed.

## PR/commit relacionado

Draft PR deste checkpoint mestre de 30/09/2026.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
