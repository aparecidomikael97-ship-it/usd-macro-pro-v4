# AION P0/H0 — cinco testes Outbox antigos migrados para contrato negativo (21/10/2026)

**Estado: LAB isolado, HARD NO-GO, 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND.**

## Evidência e escopo

A Quality da [PR #1389](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39594396764) executou 6.895 testes, registrando **50 FAIL + 32 ERROR**. Os erros antigos de Outbox/Saga incluem respostas `PermissionError: INDEPENDENT_PRODUCER_NOT_ENROLLED`, `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` e `INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED`. A negativa é necessária: em LAB não há fornecedor/custódia externa autenticados.

Esta PR **não modifica o código de produto** de Outbox, Saga, Worker, SQL/SQLite ou aprovação. Ela altera exclusivamente o contrato de **cinco métodos de teste anteriores** em `test_atlasquant_aion_execution_outbox.py`, preservando os identificadores canônicos para o inventário histórico de 85 ocorrências. Não utilizamos mocks para remover as barreiras, bypass de método privado, skip, xfail ou alteração do registro histórico.

### Cenários preservados no escopo efetivamente suportado

| Teste original | Contrato de segurança exigido nesta revisão |
| --- | --- |
| `test_lost_response_after_effect_requires_reconcile_and_never_blind_resends` | Negar o primeiro envio; injetar **apenas em SQLite temporário** um estado UNCERTAIN histórico; negar consulta a adapter e nova reserva |
| `test_unverified_absence_never_allows_retry_even_if_fixture_knows_no_effect` | Fake de não-efeito não habilita reenvio nem leitura de fornecedor não matriculado |
| `test_same_aggregate_is_ordered_until_previous_intent_is_terminal` | Bloqueio `BLOCKED_PRODUCER` do primeiro item retém segundo item em `PENDING`, sem violar FIFO |
| `test_sent_without_confirmation_is_reconciled_not_redispatched` | Um marcador SENT artificial exige prova independente; `reconcile` é negado antes de acessar adapter |
| `test_unexpired_claim_still_dispatches_once` | **Nome legado não indica capacidade atual**: ainda que haja lease válido e aprovação local, nenhum envio ao adapter é autorizado |

As linhas SQLite modificadas diretamente pelos testes são **preparação adversarial do cenário**, não ação do produto nem evidência de fornecedor. O restante verifica que o código operacional **não muda** o registro após consulta negada e **não cria** efeito confirmado. Um falso `UNCERTAIN`/`SENT` não constitui prova de envio real ou não-envio.

### Limite importante de cobertura

Os testes anteriores cobriam comportamentos que hoje **não podem executar** sem um provedor confiável: resposta perdida *depois de um efeito real*, transições reais `SENT`/`CONFIRMED`, CAS com confirmação externa, e recuperação positiva. Eles não podem ser considerados homologados porque um novo assert negativo passa. Para recuperar **cobertura funcional positiva** será necessária uma camada de testes/integração diferente, com raiz independente, fornecedor real isolado, primeira reserva externa, recibo de origem, fence, histórico completo e aprovação do proprietário. Isso **não existe neste LAB**.

### Critério de aprovação limitado

1. Os cinco métodos originais e seis casos existentes de barreira passam no Ubuntu e Windows (CI específica).
2. O inventário antigo permanece intacto e executável; os 64 casos de negação causal A79 continuam verdes.
3. A Quality **completa** roda no SHA final, com casos FAIL/ERROR comparados um a um; não extrapolar uma queda nas contagens como segurança operacional.
4. Falhas restantes não são dispensadas e nenhuma ação sai para serviço externo.

**Nenhum P0 homologado, Worker desligado, main inalterada, sem merge/deploy nem despesas novas.**
