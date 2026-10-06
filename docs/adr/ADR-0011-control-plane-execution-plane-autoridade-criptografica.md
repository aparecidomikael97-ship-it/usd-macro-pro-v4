# ADR-0011 — Control Plane separado do Execution Plane e autoridade criptográfica

- Título: Control Plane separado do Execution Plane e autoridade criptográfica
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION sustenta múltiplos domínios, agentes, memória, tarefas e capacidades. Estados
como health, readiness, memória validada ou aprovação não podem ser convertidos em
autoridade por interpretação do modelo.

## Problema

Se o LLM, payload, board, memória ou agente puder fabricar a própria autoridade,
qualquer evolução futura do ecossistema pode criar privilege escalation ou execução
indevida.

## Alternativas consideradas

Foram rejeitados: autoridade declarada por prompt; flags booleanas fornecidas pelo
caller; aprovação implícita por health; chaves compartilhadas dentro do runtime do
agente; algoritmo criptográfico próprio.

## Decisão

O AION mantém dois planos permanentes:

1. Control Plane: identidade, trust root, política, autoridade, approval, capability,
   orçamento e governança.
2. Execution Plane: executa apenas capacidades que tenham sido explicitamente
   concedidas e verificadas pelo Control Plane e pelos gates operacionais.

A autoridade criptográfica usa statements canônicos assinados e trust roots públicos
versionados. O LLM/agente nunca é raiz de confiança.

## Consequências

Uma assinatura válida pode verificar autoridade, mas não implica approval nem
execution_allowed. O gate de execução deve compor múltiplas evidências independentes.

## Componentes afetados

AION Core, authority verifier, capability registry, approval inbox, worker runtime,
tenant isolation, policy kernel e Checkpoint Mestre.

## Segurança

Chaves privadas não residem no repositório. Trust roots são material público
provisionado administrativamente. Replay protection deve ser persistente. Rotation e
revocation são obrigatórios.

## Compatibilidade

V2.10–V2.12 permanecem fail-closed. O V2.13 adiciona uma fonte real de verificação sem
alterar automaticamente o estado de execução.

## Rollback/migração

Falha no verificador, trust root ausente, chave desconhecida/revogada, binding
incompatível ou replay resultam em BLOCKED.

## PR/commit relacionado

V2.13 — branch `integration/aion-v213-real-trust-root-authority-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
