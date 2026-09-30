# ADR-0028 — Primeiro piloto do AION Business deve ser estreito, humano e explicitamente aprovado

- Título: Primeiro piloto do AION Business deve ser estreito, humano e explicitamente aprovado
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O Painel Mestre Business já separa DEMO, PILOT e LIVE. O próximo passo é definir
como um futuro primeiro piloto poderia ser conduzido sem transformar readiness em
autorização operacional.

## Problema

Um piloto amplo demais, com vários clientes, fluxos e integrações simultâneos,
dificulta atribuir falhas, medir valor, controlar capacidade e reverter riscos.

Também seria perigoso tratar "todos os testes passaram" como autorização para
contato, publicação, cobrança ou runtime.

## Decisão

O primeiro piloto deve nascer com limites rígidos:

- um cliente;
- um workflow;
- poucos canais;
- duração curta;
- operador humano;
- responsável de suporte;
- métricas e amostra definidas;
- condições de parada explícitas;
- rollback e integrações revisados;
- aprovação humana separada.

Nesta V1, todas as capacidades externas continuam desligadas. A saída máxima é
um packet `HUMAN_PILOT_APPROVAL_REQUIRED`.

## Consequências

O sistema ganha um caminho auditável entre DEMO e um eventual piloto real, sem
pular diretamente para operação.

## Segurança

Nenhum charter, gate ou packet deste ADR autoriza runtime, contato, cobrança,
publicação, contrato, credencial, deploy ou ação externa.

## Compatibilidade

ADR-0027 define o Painel Mestre DEMO/PILOT/LIVE. Este ADR detalha a governança
da camada PILOT.

## Rollback

Módulo read-only/readiness; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
