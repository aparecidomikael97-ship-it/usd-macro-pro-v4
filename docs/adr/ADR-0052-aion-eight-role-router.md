# ADR-0052 — Roteamento dos oito papéis do AION é determinístico, bounded e sem expansão de autoridade

Título: Roteamento dos oito papéis do AION é determinístico, bounded e sem expansão de autoridade  
Data: 2026-09-30  
Status: ACCEPTED

## Contexto

ADR-0047 definiu um único AION com oito papéis lógicos internos. Faltava a
camada operacional de seleção desses papéis por tarefa.

## Problema

Ativar todos os papéis em toda tarefa desperdiça custo, aumenta ruído e pode
confundir especialização com autoridade.

## Alternativas consideradas

1. Todos os oito papéis sempre ativos.
2. Oito IAs independentes permanentes.
3. Um roteador determinístico que seleciona apenas os papéis relevantes.

## Decisão

Adotar a alternativa 3.

O roteador:
- sempre mantém o Orquestrador;
- seleciona até três papéis adicionais por tarefa;
- usa no máximo quatro papéis ativos por solicitação;
- lê a lista oficial de oito papéis do Checkpoint Mestre validado;
- falha fechado se o registry do checkpoint estiver incompleto ou adulterado;
- eleva o nível de revisão para tarefas críticas;
- inclui Guardião/Executor em intenções críticas, sem conceder execução.

## Consequências

O AION permanece um único núcleo e ativa especializações sob demanda. O desenho
reduz custo e evita manter oito modelos independentes ligados.

## Segurança

Roteamento não é autorização. Nenhum papel:
- amplia permissão;
- grava memória automaticamente;
- chama modelo pago automaticamente;
- aumenta orçamento;
- executa deploy/merge;
- movimenta dinheiro;
- publica;
- opera Trade real.

Ações críticas continuam em gates independentes.

## Compatibilidade

Complementa ADR-0047 e reutiliza o Checkpoint Mestre/ADR-0051 como fonte dos
papéis oficiais.

## Rollback/migração

A camada é read-only. Removê-la mantém os routers de domínio existentes.

## PR/commit relacionado

Draft PR AION Eight Role Router V1.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
