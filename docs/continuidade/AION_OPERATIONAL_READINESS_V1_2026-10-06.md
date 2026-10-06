# AION Operational Readiness V1 — Draft isolada

Base imutável de referência: AION Core V1 Technical Closure Candidate #951,
`662eab4dc4f5bb009fa1ca89f87530df74d30ddf`.

## Autorização

Implementação autorizada pelo HUMAN_OWNER em 2026-10-06 exclusivamente em Draft
isolada, sem merge, deploy ou escrita no runtime.

## Objetivo

Fechar três gaps operacionais sem reabrir o Core V1:

1. Temporal Project Memory V2.
2. Controlled Execution Handoff V1.
3. Developer Physical Execution V1.

## Limites

Esta branch não autoriza:

- merge em main;
- deploy;
- alteração do runtime/checkpoint oficial;
- assinatura/nonce/Core Freeze;
- Worker arming/activation;
- produção;
- movimentação financeira;
- trading real;
- alteração de segredo/credencial;
- autoelevação de permissão;
- controle direto de ferramenta por IA externa.

## Temporal Project Memory V2

A memória temporal preserva evento, data, evidência, estado, relações de
supersessão e resultado UNKNOWN quando a evidência não está ingerida. Histórico
não é autoridade operacional.

## Controlled Execution Handoff

Um handoff READY apenas permite que um executor de capability separado revalide
a decisão. Ele não executa nada e não carrega autoridade raiz.

## Developer Physical Execution

O primeiro slice define os requisitos de prova física. O estado só pode chegar
a READY_FOR_PHYSICAL_EXECUTOR quando evidência independente e ligada ao mesmo
handoff/input comprovar Windows, executable pinning, filesystem/network/process
isolation, budgets, symlink/hardlink/TOCTOU e sandbox identity.

Mesmo READY não executa. A próxima camada, a ser validada em host Windows
autorizado, deverá produzir receipt atribuído e começar em OUTCOME_UNKNOWN.

## Definition of Done desta Draft

- testes focais verdes;
- Quality tests verdes;
- red-team de falsificação/tamper;
- nenhum caminho de merge/deploy/runtime;
- #951 inalterado;
- gaps físicos não podem ser convertidos em sucesso por flags do chamador.
