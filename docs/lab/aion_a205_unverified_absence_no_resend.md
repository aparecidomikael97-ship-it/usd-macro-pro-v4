# AION A205 — declarações de ausência e rejeição do adapter não autorizam reenvio

**28/10/2026 UTC · laboratório Draft · HARD NO-GO · 0/6 P0 homologadas.**

## Premissa

A204 impediu que uma resposta negativa atrasada substituísse uma
confirmação posterior. Contudo, **mesmo uma resposta imediata**
`adapter.reconcile` dizendo `found=false,
authoritative_absence=true` não comprova que o provedor externo
**não executou** a ação. O adapter é fornecido pelo próprio chamador,
não é autoridade independente nem atestado causal `NO_EFFECT_FENCED`.

Outra rota em `ExecutionOutbox.dispatch_claimed` transforma
`accepted=false,retryable=true` em `RETRY`, mesmo depois de
`adapter.send` já ter atravessado a fronteira do efeito.
`accepted=false,retryable=false` marca `FAILED`, mas a falsidade
do callback tampouco prova ausência de efeito. A regra robusta local
é tratar **todos os resultados não confirmados depois de invocar SEND**
como `UNCERTAIN`, até haver prova externa independente.

## Plano de prova RED-first

`labs/test_a205_unverified_adapter_absence_no_resend.py` usa
a implementação real Outbox/SQLite e adapter inteiramente sintético.
O fake registra um efeito e então:
1. lança timeout após efeito, e `reconcile` mente dizendo ausência;
2. retorna `accepted=false,retryable=true`, embora tenha registrado efeito;
3. retorna rejeição não retryable após registrar efeito;
4. retorna confirmação, que deve continuar criando o ledger local;
5. retorna `SENT` e depois mente dizendo ausência.

Nenhum endpoint, token, serviço real ou rede. O veredicto de prova
nativa é `UNCERTAIN`/ `SENT` retidos, nenhuma nova elegibilidade
de claim e `ABSENCE_UNVERIFIED_HARD_NO_GO` ao invés de RETRY.
Um fake pode provar que **o código não confia** na declaração;
não pode provar que um provedor real mantém ausência de efeitos.

Primeiro executar em GitHub Ubuntu/Windows **sem modificar** o código
produtivo e preservar os logs RED. Depois, caso reproduzido, alterar
os dois pontos de transição de forma mínima, preservar a suíte de
concorrência A202–A204 e registrar migração explícita dos dois testes
legados que esperavam RETRY sob prova apenas simulada. Não ocultar
falhas com skip/xfail.

## Evidências de reprodução e mitigação (RED → patch → CI)

**RED antes do patch:** [workflow A205 #40611920320](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40611920320), **4 FAIL em 14 testes no Ubuntu e 4 FAIL em 14 testes no Windows**; as 10 verificações de regressão A202–A204 passaram. Falhas reais de contrato: `RETRY != UNCERTAIN` após falso atestado de ausência, `RETRY != UNCERTAIN` após rejeição retryable, `FAILED != UNCERTAIN` após rejeição não retryable apesar de efeito sintético, e `RETRY != SENT` após ausência falsa. Um callback sintético registrou um efeito antes de mentir; não houve efeito externo real.

**Correção de laboratório:** em `dispatch_claimed`, qualquer `accepted != True` retornado *após* `adapter.send` preserva `UNCERTAIN`, com `last_error=ADAPTER_REJECTION_UNVERIFIED`. Uma atualização CAS de snapshot `state='UNCERTAIN'`, `lease_owner`, `lease_until` e `dispatch_started_at` impede que a rejeição sobrescreva mudança concorrente. Em `reconcile`, `found=False,authoritative_absence=True` de adapter autocontrolado não abre mais `RETRY`: retorna o estado atualizado e `ABSENCE_UNVERIFIED_HARD_NO_GO`, ou `NOT_RECONCILED_STATE_CHANGED` se outro fluxo avançou. O antigo ramo de RETRY por ausência fica **inacessível** após retorno incondicional, mantido apenas para auditoria. Confirmações sintéticas continuam sendo escritas no ledger local, mas tampouco são homologação de receipt causal real.

**Migração de contratos legados:** `test_atlasquant_aion_execution_outbox.test_authoritative_absence_allows_retry_after_lost_pre_effect_attempt` (que simulava prova de ausência e dois envios) foi reescrito como `test_self_reported_absence_after_lost_ack_never_authorizes_retry`. `labs/test_a204_outbox_stale_absence_confirmed.test_03_current_absence_of_uncertain_can_remain_retryable_in_lab` foi renomeado para exigir `UNCERTAIN` retido. Os testes originais continuam preservados integralmente no commit ancestral `674494d79cd86f11e8fd9af1480b695d2e28a35e` e no diff; não houve `skip`, `xfail` nem supressão de falha. Os testes de verdadeiros efeitos de produção **não foram executados**.

**Limitação operacional explícita:** este bloqueio pode deixar uma intenção em `UNCERTAIN` indefinidamente até haver uma autoridade de reconciliação independente. É preferível a duplicar um pagamento/ordem/mensagem. **Não** existe reativação por configuração ou por autorização local; para permitir novo envio serão necessários novo projeto e provas externas H0 homologadas. Não retirar a restrição pelo CI verde.

## Requisitos externos ainda ausentes

Raiz HUMAN_OWNER original independente, CAS de intenção semântica
originária, custódia monotônica contra rollback conjunto, recibo
causal e `NO_EFFECT_FENCED` de provedor independente, SQLite nativo
contra restauração/inode. `UNCERTAIN=ZERO_AUTO_RESEND`.
Não se libera SEND real por resultados verdes de CI.

Sem contratação, AWS/KMS, pagamentos, ordens, Worker,
merge, deploy ou B2B Negócios. Gastos posteriores a 06/11
somente com aprovação expressa do proprietário.
