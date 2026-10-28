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

### RED antes da correção — logs reais preservados

- [A202 #40605487544](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40605487544) apresentou **ERROR no Ubuntu** por um erro **do fixture**, que tentava usar uma conexão SQLite criada numa thread em outra (check_same_thread=True). Esta primeira execução NÃO comprova duplicação.
- Corrigimos o fixture para que cada thread construa seu próprio `SQLiteChatStore`, com duas conexões independentes, sincronizadas após leitura e autorização.
- [A202 RED #40605588340](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40605588340), na **implementação anterior sem CAS checado**, reproduziu **uma colisão real do registro local de efeitos no Ubuntu e Windows**. Logs: `ValueError: effect ledger idempotency collision`. O adapter sintético registra referências de efeito diferentes a cada chamada: o erro só acontece quando as duas execuções chegaram a `adapter.send`, ainda que o SQLite tenha permitido apenas uma transição `CLAIMED` → `UNCERTAIN`. Não houve provedor real.

### Patch mínimo e GREEN

O código real `ExecutionOutbox.dispatch_claimed` agora mede o `cursor.rowcount` da atualização `CLAIMED` → `UNCERTAIN` que inclui o escopo, o mesmo `worker_id` e o `lease_until` observado. Só o vencedor (rowcount == 1) entra em `adapter.send`; o perdedor retorna `dispatch_state=NOT_DISPATCHED_STATE_CHANGED`, sem segundo envio nem reenvio cego. A transição é persistida **antes de qualquer efeito** e o resultado do perdedor não é um recibo externo.

[A202 corrigida #40605732278](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40605732278): **3/3 PASS no Ubuntu e 3/3 PASS no Windows**, com duas conexões reais. O fixture não foi silenciado nem marcado como skip/xfail. Os dois testes complementares preservaram a proibição de replay após CONFIRMED e a recusa sem SEND na revogação.

Estes testes demonstram somente o CAS local para duas conexões no mesmo arquivo SQLite; não demonstram efeitos externos exatamente uma vez, nem resistência à restauração do banco/host.

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
