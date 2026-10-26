# AION G118 — recuperação assinada não comprova efeito do fornecedor (LAB)

**Data:** 26/10/2026. **PR:** #1608 Draft, base G117 #1607. Código testado `88568f2b0ba10ea61337c511eff9d8e938973416`. **0/6 P0 HOMOLOGADAS; HARD NO-GO**. Nenhum merge, deploy, Worker ou SEND real.

## Contrato implementado

`labs/a190/g118_signed_witness_recovery_lab.py` exige cliente G114 que verifica assinatura Ed25519 e challenge. Executa apenas `status(event_id)`, nunca `reserve`, `send`, `bootstrap` ou confirmação de provedor. Resultado `RecoveryObservationLab` imutável possui, em QUALQUER caso: `provider_outcome=UNKNOWN`, `allow_send=False`, `allow_retry=False`, `may_mark_provider_confirmed=False`.

Prova assinada de reserva = um registro de **intenção gasta no custodiante de teste**, não uma prova de que uma operação chegou/foi executada pelo provedor. Até `NOT_FOUND` e `ENROLLED` válidos NÃO demonstram que nenhum efeito real já ocorreu, porque o histórico host-controlled pode sofrer rollback. Um high-water anterior detecta restauração apenas se preservado fora da restauração, o que não existe neste LAB.

## Resultado objetivo

[GitHub Actions G118 40378485708](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40378485708), ambos os jobs SUCCESS:

| Testes executados | Ubuntu | Windows |
| --- | ---: | ---: |
| G118 + G115 herdados | 34/34 PASS | 34/34 PASS |
| G116 herdados | 24/24 PASS | 24/24 PASS |
| G114 originais | 15/15 PASS | 15/15 PASS |

A contagem 34 contém 11 testes G115 executados duas vezes (importação da classe base e herança), mais 12 métodos novos G118: **23 métodos distintos**, não 34 controles novos. O workflow anterior já executava 34 com `OK`, mas estava vermelho porque seu `grep` esperava 23; o único ajuste foi exigir `Ran 34 tests`, sem alterar código/teste/segurança.

As 12 situações novas cobrem: `ENROLLED` sem liberação de retry; `RESERVED` não como recibo de fornecedor; ACK perdido + reinício; Outbox real de LAB permanecendo UNCERTAIN com 0 sends do adaptador falso; `NOT_FOUND` sem prova de ausência; chave ausente/falsa; identidade de solicitação ou origem alterada; restauração do ledger com/sem contador local preservado; segundo evento distinto elevando high-water; objeto não assinado rejeitado; resultado imutável sem método de envio.

## Limites e próxima prova

Chave de assinatura, cadastro de origem, transporte e segundo arquivo SQLite continuam na MESMA máquina sob custódia do test harness. O teste `G118_RESET_LOCAL_FLOOR=STILL_NOT_EXTERNAL_ANTIROLLBACK` mostra o risco remanescente. A G118 não produz, valida nem substitui um recibo do fornecedor. A verificação de Quality/Security canônicas foi feita sobre o código anterior G116 em G117, **não reexecutada ainda sobre G118**.

Próxima tarefa LAB recomendada: definir um segundo contrato de **evidência do fornecedor**, com raiz/pin DOMÍNIO SEPARADO, vínculo a evento/efeito/decisão e verificação de nonce, mas sem transformá-lo em autorização de retry ou alegação de prova externa independente. A homologação real depende de custódia monotônica fora do host, inscrição original não controlada pelo chamador, atestação VFS SQLite e antirollback nativo.

**0/6 P0 HOMOLOGADAS. HARD NO-GO. Sem merge/deploy/Worker/SEND real/fundos.**
