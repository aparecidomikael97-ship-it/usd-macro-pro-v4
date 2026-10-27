# AION A202 — teste adversarial do CAS de saída Outbox (LAB)

**27/10/2026 · PR Draft · HARD NO-GO, 0/6 P0 homologadas.**

## Hipótese a falsificar

`atlasquant_aion_execution_outbox.ExecutionOutbox.dispatch_claimed`
lê a intenção com `state=CLAIMED`, revalida a autorização e grava
`state=UNCERTAIN` em SQLite antes de chamar `adapter.send`. Porém,
o comando de atualização só usa `WHERE state='CLAIMED'` e **não verifica
`cursor.rowcount`**. Sob duas conexões SQLite e o mesmo `worker_id`,
as duas chamadas podem validar o estado antigo e apenas uma transicionar
a linha. Se a segunda não identificar o CAS perdido, poderá alcançar SEND.
Este é um risco de reentrância local mesmo antes dos seis bloqueios externos.

## Prova inicial do laboratório — antes do patch

`labs/test_a202_outbox_dispatch_atomic_cas.py` cria um SQLite real em WAL,
duas conexões `SQLiteChatStore` distintas e duas instâncias Outbox para a
mesma intenção e mesmo `lease_owner`. `threading.Barrier` pausa as duas
depois de autenticar, antes do comando `UPDATE`; um adapter local e sintético
conta **todas** as chamadas a `send` sem de-duplicar. Esperado de um Outbox
seguro: exatamente uma chamada ao adapter, uma transição `CONFIRMED`
e uma saída `NOT_DISPATCHED_STATE_CHANGED`. **Não é efeito real; não conecta
provedor, GitHub API ou rede.**

A primeira rodada do workflow A202 deve apresentar RED na implementação
antiga se a hipótese estiver correta. Só depois de observar os logs,
implementar CAS transacional com `rowcount == 1` e comportamento fail-closed,
sem retry cego em `UNCERTAIN`.

## Limitações externas mantidas

Mesmo um CAS SQLite local correto não prova identidade original
HUMAN_OWNER externa, primeira reserva monotônica não restaurável,
autoridade de custódia independente ou recibo causal provider H0.
Outbox é staging, não serviço de SEND habilitado; nenhuma chamada a
provider pode ser autorizada apenas por `authorize` do chamador.
`UNCERTAIN=ZERO_AUTO_RESEND`. 0/6 P0 homologadas.

**Governança:** B2B Negócios congelado. Sem novos serviços ou gastos até
05/11, nem depois sem aprovação expressa. Sem AWS/KMS, deploy, Worker,
trades, provider real, chaves reais, merge ou pagamento.
