# A190 G3 — evidência objetiva CI Ubuntu/Windows e controle RED

**Fuso do proprietário:** 2026-10-23. **PR:** #1490 (DRAFT, sobre #1489). Missão #1486.

## Proveniência executada

- **SHA EXATO de código, workflow e contrato exercitados:** `7813679c1e4013d18e5c59f3cefb98eb30693b44`.
- **GitHub Actions run #40045624664:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40045624664
- **Estado da execução:** `completed / success`, conferido por metadados do GitHub Actions; logs de ambos jobs conferidos individualmente.
- **Job Ubuntu** `120726554919`: `completed / success`; linha `Ran 26 tests in 0.105s`, `OK`; SHA de checkout conferido.
- **Job Windows** `120726554746`: etapa de testes e de pós-validação `success`; `Ran 26 tests in 1.457s`, `OK`; SHA de checkout conferido.
- **Matriz por sistema:** 10 casos preexistentes A183 + 10 casos preexistentes A189 + **6 novos casos G3** = **26 casos em cada OS, 52 execuções no conjunto**.
- Dependências já utilizadas na trilha A184: `cryptography==50.0.2` e `requests==2.34.2`; executores efêmeros `ubuntu-latest` e `windows-latest`, Python 3.12.

## Marcadores nos DOIS jobs

| Marcador real | Resultado de laboratório, NÃO homologação |
| --- | --- |
| `A190_G3_SAME_CLAIMED_EVENT=DENIED_LOCAL_AND_VERIFIER_INSTANCE` | Mesma alegação de ID não gera outra reserva local |
| `A190_G3_SIGNED_DIFFERENT_IDS_SAME_ORIGINAL=DOUBLE_LOCAL_RESERVATION_RED` | **RED**: reetiquetar um mesmo evento sintético com ID novo admite duas reservas, mesmo com assinaturas fixture |
| `A190_G3_SELF_PINNED_FAKE_RECEIPT=LAB_VERIFIED_BUT_EXTERNAL_AUTHORITY_RED` | **RED**: quem consegue substituir seus próprios pins e raiz pode produzir recibo local verificável |
| `A190_G3_ACK_LOSS=UNCERTAIN_ZERO_AUTO_RESEND` | ACK perdido não libera reenvio automático |
| `A190_G3_POST_ACK_LOSS_NEW_UNAUTHENTICATED_ID=DOUBLE_RESERVATION_RED` | **RED**: ID distinto autoalegado após timeout admite segunda reserva sem provar nova intenção |
| `A190_G3_MISSING_PROVIDER_RECEIPT=DENIED_NOT_SUCCESS` | Ausência de recibo não é classificada como sucesso |
| `A190_G3_FIXTURE_RECEIPT=NEVER_PERMITS_REAL_EFFECT` | Recibo fixture não autoriza enviar/repetir |
| `A190_G3_UNTRUSTED_EVIDENCE_CALLBACK=SIDE_EFFECT_PRECEDES_DENIAL_RED` | **RED de integração:** callback arbitrário pode mutar memória antes da negativa do verificador |

## O que NÃO foi testado / cláusula de recusa

1. **Zero operação real:** não houve cobrança, ordem, transferência, mensagem ao cliente, chamada de fornecedor, credencial real ou Worker.
2. As quatro chaves Ed25519 são derivadas de bytes sintéticos conhecidos pelo mesmo processo; nem a origem dos eventos nem os emissores são independentes. Recibo `RECEIPT` aqui é somente estrutura assinada; **não** comprova execução.
3. Os dois runners rodam testes Python/SQLite, mas G3 **não** testou dois principais reais nem a identidade do emissor ou fornecedor; esses controles G1/G2 são outro escopo.
4. `52 execuções OK` significa que as hipóteses de proteção parcial e **bypasses** foram reproduzidas. NÃO transformar o G3 nem qualquer P0 em aprovado.
5. Quality/Security completas, cinco external-RED por OS e 43 advisories herdados **não reexecutados neste G3**; baseline continua pendente. Idempotência externa, recibo de efeito, monotonicidade independente, H0, WAL/SHM/VFS, ABA e revogação real igualmente pendentes.

**Conclusão factual:** componente atual não consegue provar única primeira tentativa para um evento de origem autoalegada, ainda que assinaturas sintéticas sejam válidas. A proposta de integração depende de emissor original independente e autorização/idempotência semântica de fornecedor, ambos ausentes.

**Não alterar status:** `0/6 P0` — `HARD NO-GO` — `UNCERTAIN` — `ZERO_AUTO_RESEND`. Somente LAB/Draft, sem merge/main/deploy/Worker/serviço pago/gasto novo.
