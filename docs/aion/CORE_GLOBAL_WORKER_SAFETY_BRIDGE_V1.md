# AION Core — Global Worker Safety Bridge V1

## O que foi conectado

O Global Durable Worker passa a consultar o Loop Governor que já existe em
`atlasquant_aion_loop_governor.py` antes de qualquer execução. A função é
`evaluate_global_worker_loop`, chamada por `run_global_worker_once`.

O plano é determinístico. Cada nó pode carregar `node_id`, `parent_id`,
`tenant_id`, `workspace_id`, `capability`, `schedule_id`, `occurrence_key`,
risco e um contexto de recurso. O tenant e o workspace confiáveis vêm somente
do contexto autenticado reconstruído da delegação já armada. Um tenant ou
workspace escrito no payload do schedule não vira contexto confiável. Se o
claim for uma string diferente, o governor devolve `SCOPE_MISMATCH`. Se o
claim não for string, o tick fecha em `CLAIM_TYPE_INVALID`. Bool, número e
string `"true"` não são tratados como verdadeiro.

Se o governor bloquear, o executor não é chamado, o lease não é reivindicado,
a reconciliação inflight existente continua tendo prioridade e nenhum Action
Receipt é fabricado. O estado do tick é `LOOP_GOVERNOR_BLOCKED`, não sucesso.

Quando o executor produz um child receipt legítimo, o envelope já selado por
`seal_executor_receipt_envelope` é apenas encaminhado na resposta. O child
receipt permanece o registro primário, no namespace do executor. O envelope
referencia o `receipt_id`, o fingerprint canônico, a capability, a occurrence
key, o estado do guardian e os digests de autorização e resultado quando
existem.

## O que permaneceu desligado

- Global Worker continua OFF sem arming explícito e sem a feature flag exata.
- Kill switch, lease, fencing token, CAS, inflight, idempotência e tetos de
  recurso continuam no caminho.
- Não há subprocess, shell, pagamento, publicação, deploy, trading ou segredo
  proposital em log ou receipt.
- Runtime de produção não foi ativado.
- Nenhum provider pago foi chamado por este contrato.

## Loop Governor

O governor é um gate pré-execução. `WITHIN_LIMITS` não concede permissão e não
inicia worker. Os limites usados pelo Global Worker são profundidade 2,
fan-out 8 e 16 nós, todos dentro dos tetos já publicados pelo governor
(4, 8 e 32). Esses tetos não foram aumentados. Tipo inválido de limite falha
fechado.

## Action Receipt

O Action Receipt é evidência. `authorization` permanece `NONE`.
`action_receipts_are_authority` permanece falso. O envelope não arma worker,
não aprova tarefa, não libera entitlement, produção, trading ou pagamento, e
não substitui aprovação humana. Um child receipt sem `receipt_id` não é
selado. Alterar o child receipt muda o fingerprint.

## Persistência

Não foi criado storage externo para o envelope. A arquitetura atual já
persiste o child receipt no checkpoint do executor. O envelope fica só na
resposta em memória, com `external_persisted=false` e
`action_receipt_external_persisted=false`. Isso evita crescimento duplicado
de receipts no checkpoint.

## O que este registro não afirma

- Multi-instância real não está confirmada.
- Operação 24/7 real não está confirmada.
- Produção não foi executada.
- Deploy não foi executado.
- Trading real não foi executado.

## Checkpoint

- Branch: `cursor/aion-global-worker-safety-bridge-v1-8499`
- Base SHA: `ba50e91804c71b0d2ff6a1f52979cc1a687792ff`
- HEAD SHA: registrado na Draft PR desta branch
- Global Worker: OFF por padrão; esta ponte não o arma
- Produção: não ativada
- Deploy: não executado
- Trading real: não executado

## Testes deste registro

- Alvo: `test_atlasquant_aion_loop_governor.py`, `test_atlasquant_aion_action_receipt.py`, `test_atlasquant_aion_action_receipt_bridge.py`, `test_atlasquant_aion_worker_runtime.py`, `test_atlasquant_aion_global_worker.py` — 102 OK
- Suíte completa: `python3 -m unittest discover` — 3884 OK
- `python3 -m compileall .` — OK
- Nenhum arquivo novo de teste; `test_atlasquant_aion_global_worker.py` já está no workflow de qualidade

CONFIRMADO neste contrato: o governor roda antes do executor no caminho do
Global Worker; bloqueio impede a chamada; o child receipt continua primário; o
envelope não autoriza.

NÃO VERIFICADO: execução física em runtime GitHub, multi-instância real,
operação contínua 24/7, SHA de produção.

BLOCKED: ativação do worker, deploy, provider pago, trading real, merge em
main, e qualquer escrita na trilha da PR #470.
