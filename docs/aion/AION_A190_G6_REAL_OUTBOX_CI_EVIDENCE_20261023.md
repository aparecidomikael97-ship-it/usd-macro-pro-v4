# A190 G6 — evidência CI da fronteira de confiança REAL no ExecutionOutbox

**Dia local do proprietário:** 2026-10-23. **PR Draft #1493**, empilhada sobre G5 #1492; missão #1486.

## Proveniência técnica conferida

- **Commit de código/workflow/preflight executado:** 4f71d239616d98ccde67684079f72fff078e1f99.
- **Execução GitHub Actions:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40046910256 — status completed, conclusion success.
- **Ubuntu job 120730639664:** completed/success, 38 tests in 2.428s, OK; marcadores adversariais presentes.
- **Windows job 120730639952:** completed/success, 38 tests in 6.647s, OK; marcadores adversariais presentes.
- **Contagem sem arredondamentos:** 8 casos G6 + 5 G5 + 5 G4 + 6 G3 + 10 A189 + 4 A185 = 38 por SO, **76 execuções**. Python 3.12 com SQLite real e adapter de contagem **somente em memória**.
- O CI de G6 não adiciona cobertura de fornecedor externo, nem executa Quality/Security canônicas completas.

## Matriz de prova e de falha honesta

| Marcador G6 nos dois sistemas | Natureza | Interpretação |
| --- | --- | --- |
| A190_G6_NO_FIRST_ATTEMPT_GUARD=REAL_OUTBOX_NO_SEND | POSITIVO | Outbox real nega adapter.send quando não existe guarda |
| A190_G6_A183_SIGNED_FIXTURE_PERMITS_SEND_FALSE=REAL_OUTBOX_NO_SEND | POSITIVO | Uso correto de A183.permits_send=False nega, mesmo com lab_verified=True |
| A190_G6_FIRST_ATTEMPT_WITNESS_TIMEOUT=UNCERTAIN_NO_SEND | POSITIVO | Exceção de guarda preserva UNCERTAIN e nenhuma chamada |
| A190_G6_CALLER_TRUE_GUARD_AND_RECEIPT=IN_MEMORY_SEND_CONFIRMED_RED | **RED** | Callbacks do próprio chamador que respondem True atravessam adapter e confirmam efeito puramente sintético |
| A190_G6_CALLER_TRUE_GUARD_WITHOUT_RECEIPT=ADAPTER_CROSSED_RED | **RED** | Mesmo sem verificador de recibo, a primeira callback True basta para adapter.send ser chamado; fica SENT, não CONFIRMED |
| A190_G6_VERIFIER_REPLACED_AFTER_SEND=FORGED_LOCAL_CONFIRMATION_RED | **RED** | Outra instância Outbox com evidence_verifier=True transforma recibo autoalegado em CONFIRMED |
| A190_G6_DIFFERENT_INTENT_REFS_SAME_SEMANTIC_EVENT=TWO_MEMORY_SENDS_RED | **RED** | Dois identificadores autoalegados geram duas chaves/desejos e duas chamadas em memória |
| A190_G6_A183_LAB_VERIFIED_MISWIRED_AS_AUTHORITY=SEND_BYPASS_RED | **RED** | Converter lab_verified=True de fixture de evento NÃO vinculado em guarda operável libera adapter apesar de permits_send=False |

**A palavra SEND nos marcadores** significa chamada da interface adapter.send do próprio Outbox real. O adaptador desta suíte é um objeto MemoryOnlyAdapter; nenhuma rede, subprocesso de provedor, cliente, cobrança, ordem, envio de e-mail ou efeito externo foi invocado. Estado CONFIRMED equivale a linha sintética local, NÃO recibo.

## O que a evidência muda no plano

- O seam de autorização e recibos existente oferece comportamento fail-closed no modo sem callback; isso foi exercido em ambos SOs.
- O seam NÃO autentica independentemente a callback/issuer. Um host que controle callbacks consegue, por contrato Python, produzir True. Isso é condição explícita para HARD NO-GO; uma simples assinatura local ou validação de tipo não resolve.
- Não existe vinculação atestada da callback A183 à identidade original do negócio, epoch/piso monotônico externo e consequência do fornecedor. Os requisitos do issue #1486 continuam sem autoridade independente provida.
- Nenhuma nova mudança operacional foi introduzida; entregar o teste e o ADR não protege o produto real contra um host comprometido.
- FinOps: nenhuma API paga/serviço externo foi provisionado; orçamento R$200/mês e exceção até R$250 sujeita a autorização seguem sem alteração.

## Não homologar / próximos critérios de prova

Raiz e chaves fixadas fora do aplicativo; emissor do evento independente; custodiante monotônico fora do host sujeito a rollback; idempotência semântica atestada pelo fornecedor; recibo real vinculando efeito à reserva, HUMAN_OWNER autenticamente desafiante; rechecagem H0 e política offline fail-closed. Reexecutar canônicos completos e manter external-RED até prova externa própria, sem trocar status de CI.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** Cinco external-RED por SO, 43 advisories herdados e ausência de VFS/FD/power-loss/host admin ainda pendentes. Sem merge/main/deploy/Worker/gastos/credenciais/efeito real.
