# ADR-0015 — Sandbox do AION Business deve ser determinístico e sem efeitos externos

- Título: Sandbox do AION Business deve ser determinístico e sem efeitos externos
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

O Business Expert já possui certificação e uma camada de runtime readiness que
pode preparar estado `SANDBOX_READY`, mantendo produção desligada.

## Problema

Era necessário testar comportamentos reais de negócio sem depender de provider,
rede, clientes reais, pagamentos ou publicação.

## Decisão

Criar um harness determinístico de sandbox alimentado apenas por fixtures do
chamador. Os primeiros casos cobrem FAQ, qualificação de lead, follow-up em
rascunho e Radar do Negócio.

O harness exige sessão isolada por tenant/workspace/actor/session, limita lote,
nega casos desconhecidos e bloqueia explicitamente ações externas.

## Consequências

Podemos validar fluxo e experiência do BUSINESS antes de ligar qualquer runtime.
O mesmo harness também pode apoiar demonstrações e treinamento do administrador.

## Segurança

Nenhum caso executa contato, contrato, cobrança, pagamento, gasto, publicação,
deploy, movimentação de dinheiro ou trading real.

## Compatibilidade

ADR-0014 continua sendo o gate de readiness. Este ADR adiciona apenas um executor
de simulação e não cria capacidade produtiva.

## Rollback

O harness é puro e não persiste efeitos externos; remover o módulo não exige
migração nem compensação.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
