# AION P0 — revisão externa ao mutex do STAGING: época, múltiplos processos e flags de runtime

**20/10/2026 — Diagnóstico LAB somente.** A revisão parte do [PR Draft #1350](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1350), que isolou a corrida de publicação/revogação entre threads. **Mesmo CI verde de atomicidade não homologa a identidade nem permite execução do Worker.**

## Fronteiras a distinguir

| Cenário | O que o código atual prova | O que NÃO prova |
| --- | --- | --- |
| Duas threads mesmo processo, mesmo dicionário `session_state` | `RLock` serializa os métodos de gerenciamento e revoga holders anteriores | Qual credencial é mais recente/autêntica |
| Credencial antiga autoafirmada | Hash local distingue fingerprints diferentes e revoga referência anterior ao trocar | Que o fingerprint recebido é aceito pelo emissor ou não foi revogado |
| Duas sessões ou dois processos com mesmo banco | Transações SQLite e store por chamada são independentes e permitem leitura local | Revogação conjunta dos handles após um logout num outro processo |
| 2 sessões independentes enquanto uma criação segura demora | Mutex de processo serializa as transições | SLA/throughput aceitável para usuários simultâneos |
| `runtime_context` injetado no STAGING | Flags do resultado `provider_called`, `network_called`, `external_action_executed` são False nos cenários LAB | Que flags contraditórias no contexto fornecido foram rejeitadas antes de entrar no runtime |

## Inspeção executável

`tests/test_aion_p0_staging_epoch_multiprocess_boundary_diagnostic_lab.py` tem **7 cenários locais**. Os testes 01–05 e 07 **esperam observar lacunas**, portanto `PASS` é diagnóstico e nunca `GREEN_SECURITY`. O processo filho real (via `subprocess`) abre o chat STAGING numa sessão SQLite temporária, enquanto o pai encerra sua sessão, e comprova que não há canal de revogação compartilhado. Nenhum dado pessoal ou rede externa. O teste de lock global controla I/O com `threading.Event` em sessões distintas para mostrar o atraso induzido.

A mesma CI executa os 12 casos normativos da sessão corrigida, as 17 regressões do PR #1195, 8 hardstops SQLite, chat STAGING, identidade/isolamento e um subconjunto original de `test_atlasquant_aion_security_adversarial`/ `test_atlasquant_aion_local_security_matrix`, sem excluir historicamente a Quality completa.

## Limites de uma próxima mudança produtiva

É defensável bloquear **localmente**, antes de construir store, `runtime_context` explicitamente pedindo `provider_enabled=True`, `network_enabled=True` ou `production_persistence=True`; nesse caso, impor contrato fail-closed de STAGING e testar leitura legítima. Uma fixação das flags em `False` depois da solicitação seria menos transparente que recusar o pedido.

**NÃO** é defensável tentar homologar revogação do HUMAN_OWNER usando `authenticated_at`, `last_seen`, fingerprint, contador de sessão ou wall-clock controlado pelo cliente. O autenticador externo responsável deve prover issuer, epoch monotônico, challenge/nonce e revogação autenticada, e o consumidor deve vincular isso à sessão real por canal independente. Sem esse vínculo, manter **P0 aberto / HARD NO-GO**.

As três linhas de melhoria não devem ser confundidas com a falha do primeiro efeito: nenhuma prova de ausência de SMS/pagamento/trade é fornecida por SQLite ou Streamlit.

**Estado inalterado:** 32 erros Outbox/Saga `OPEN_NOT_WAIVED`, Quality histórica completa RED 51 FAIL +34 ERROR, 0/6 P0, Worker OFF, ZERO_AUTO_RESEND. Sem merge/deploy/serviços pagos.
