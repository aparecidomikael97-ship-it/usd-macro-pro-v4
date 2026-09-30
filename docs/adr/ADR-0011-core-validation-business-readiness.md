# ADR-0011 — Validação do Núcleo e prontidão do BUSINESS antes de certificação

- Título: Validação do Núcleo e prontidão do BUSINESS antes de certificação
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O hardening do Núcleo deixou Trader, Business e Investments registrados, mas
com runtime desligado e estado `NOT_CERTIFIED`. Produção ainda precisa de prova
de identidade, o Checkpoint Mestre não pode ser promovido por narrativa e o
rollback precisa de exercício verificável antes de qualquer liberação.

## Problema

Sem um gate adicional, uma evidência parcial poderia ser confundida com
validação do Checkpoint ou com certificação do BUSINESS. Também faltava um
drill de restauração que provasse a mecânica de rollback sem tocar produção.

## Alternativas consideradas

Promover o Checkpoint apenas porque a suíte local está verde foi rejeitado.
Tratar readiness comercial como certificação técnica do especialista também foi
rejeitado. Restaurar diretamente um checkpoint de produção durante a validação
foi rejeitado por aumentar o risco.

## Decisão

Criar `ATLASQUANT_AION_CORE_VALIDATION_V1` como camada read-only. A identidade
de produção só é verificada com SHA observado, ambiente conhecido e comparação
não local. O Checkpoint Mestre só pode retornar `VALIDADO` quando integridade,
digest, identidade de produção, drill de rollback, referências de evidência e
aprovação humana explícita estiverem presentes.

O rollback deste estágio é exercitado em memória, com cópia profunda e digest
canônico. O BUSINESS pode atingir `READY_FOR_CERTIFICATION_REVIEW`, mas continua
`NOT_CERTIFIED`, com runtime e ações externas desligados.

## Consequências

Produção desconhecida permanece desconhecida. O Checkpoint não é promovido por
código presente. O BUSINESS ganha um checklist verificável de produto,
treinamento, demo, privacidade, margem, suporte e fronteiras de aprovação sem
receber autoridade de execução.

## Componentes afetados

AION Core, Build Identity, Checkpoint Mestre, Specialist Certification,
Business Expert, documentação e Quality Tests.

## Segurança

O gate não faz rede, não grava checkpoint, não ativa runtime, não autoriza merge
ou deploy, não publica, não cobra e não executa trading. Strings semelhantes a
booleano não contam como aprovação. Evidência truncada ou ausente falha fechada.

## Compatibilidade

Os contratos anteriores continuam válidos. ADR-0010 permanece responsável pelos
quatro fechamentos de especialista. ADR-0007 continua definindo o Checkpoint
Mestre como persistência oficial e ADR-0009 mantém merge/deploy sob gate.

## Rollback/migração

Remover este gate exige novo ADR. Como esta camada não persiste estado nem ativa
runtime, o rollback de código consiste em retirar o módulo, seus testes e as
referências documentais, sem migração de dados.

## PR/commit relacionado

Implementação preparada em branch de desenvolvimento empilhada sobre o hardening
da PR #394. Nenhum SHA desta branch é tratado como prova de produção.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
