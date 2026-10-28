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

## Requisitos externos ainda ausentes

Raiz HUMAN_OWNER original independente, CAS de intenção semântica
originária, custódia monotônica contra rollback conjunto, recibo
causal e `NO_EFFECT_FENCED` de provedor independente, SQLite nativo
contra restauração/inode. `UNCERTAIN=ZERO_AUTO_RESEND`.
Não se libera SEND real por resultados verdes de CI.

Sem contratação, AWS/KMS, pagamentos, ordens, Worker,
merge, deploy ou B2B Negócios. Gastos posteriores a 06/11
somente com aprovação expressa do proprietário.
