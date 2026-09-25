# AION — Tool Hub / MCP + Tarefas Duráveis

Data: 2026-09-25

## Objetivo

Dar ao AION uma camada padronizada de ferramentas e um estado de trabalho que
possa ser retomado exatamente depois de interrupção, sem transformar retomada
em autorização automática.

## Checkpoint Mestre V11

O Checkpoint passa a persistir:

- `tool_hub`;
- `durable_tasks`.

Ambas as seções possuem digest e entram no relatório de integridade.

## Tool Hub

O Tool Hub registra:

- identidade da ferramenta;
- workspace;
- conector;
- tipo de ação;
- ação Guardian;
- scopes necessários;
- efeitos externos;
- estado técnico.

Protocolos previstos:

- NATIVE;
- API;
- MCP;
- FILE;
- WEBHOOK.

O registry não chama ferramenta.

Uma ferramenta externa só pode avançar para um executor quando:

1. estiver registrada;
2. o conector estiver realmente ativado e aprovado;
3. a origem da intenção tiver autoridade;
4. o Guardian permitir;
5. a Proof of Safety aplicável passar.

`CONFIGURED` ou `READY` não equivale a execução.

Tool output continua sendo conteúdo e nunca autoridade.

## Tarefas Duráveis

Uma tarefa durável preserva:

- objetivo;
- domínio;
- missão associada;
- passos;
- cursor;
- revisão;
- geração de retomada;
- artefatos;
- evidências;
- bloqueios;
- próxima ação;
- digest de checkpoint de referência.

A retomada usa revisão/cursor e pode detectar mudança do Checkpoint.

Estados de retomada:

- RESUME_READY;
- BLOCK.

Conflitos possíveis incluem:

- revisão divergente;
- Checkpoint alterado;
- tarefa terminal.

## Regra de segurança

Retomar uma tarefa **não executa** o próximo passo.

A retomada apenas reconstrói o estado necessário para que o AION saiba:

- onde parou;
- o que já foi concluído;
- o que está bloqueado;
- qual passo vem depois;
- quais artefatos/evidências existem.

A execução real continua dependente de Tool Hub, Guardian, permissões,
Proof of Safety e aprovação quando aplicável.

## Interface

A área Desenvolvimento passa a exibir:

- quantidade de tools registradas;
- tools locais prontas;
- tarefas retomáveis;
- tarefas aguardando aprovação;
- catálogo do Tool Hub;
- pré-voo consultivo de ferramenta;
- criação de tarefa durável;
- preparação e registro de retomada.

Nenhuma dessas telas chama ferramenta externa por si só.

## Estado honesto

Implementado nesta etapa:

- contratos Tool Hub;
- preflight integrado à Fortaleza;
- estado durável;
- persistência V11;
- interface administrativa;
- testes.

Ainda não significa:

- MCP externo conectado;
- GitHub/Google/serviço terceiro ativado pelo AION;
- execução automática em background;
- autorização automática após reinício;
- trading real.

