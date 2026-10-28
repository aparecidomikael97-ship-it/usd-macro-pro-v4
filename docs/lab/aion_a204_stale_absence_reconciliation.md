# AION A204 — reconciliação atrasada não pode reabrir efeito confirmado (LAB)

**28/10/2026 UTC · Draft · 0/6 P0 homologadas · HARD NO-GO**

## Hipótese testável

`ExecutionOutbox.reconcile` carrega uma fotografia `UNCERTAIN` ou
`SENT`, chama o callback `adapter.reconcile`, e quando este retorna
`found=false, authoritative_absence=true`, grava `state=RETRY` no
SQLite com um UPDATE **sem condição do estado já existente**.
Uma confirmação posterior à fotografia, porém anterior ao UPDATE,
pode ser substituída por RETRY, tornando uma intenção já confirmada
novamente elegível para dispatch. O mecanismo de controle A203 sobre
revogação atrasada não cobre este outro caminho.

## Método: RED-first, sem provedores

`labs/test_a204_outbox_stale_absence_confirmed.py` usa duas conexões
SQLite reais em threads diferentes e duas fontes de reconciliação
**falsas**. Um Event pausa a reconciliação com resposta negativa
antiga enquanto uma nova confirma o mesmo efeito sintético no ledger.
O evento então libera a ausência atrasada. São testados dois estados
iniciais: `UNCERTAIN` após ACK sinteticamente perdido, e `SENT`
após aceite sem confirmação. Em ambos, o resultado correto é preservar
`CONFIRMED`, o ledger com efeito único e nenhuma fila de RETRY.
Há controle separado em que uma ausência imediata pode retornar RETRY
apenas no modelo sintético já existente.

A primeira execução serve como evidência *antes da correção*, não
deve ser reinterpretada como sucesso se houver erro de fixture.
Após reproduzir o problema, corrigir usando compare-and-set contra
a fotografia de reconciliação, verificar `cursor.rowcount`, e
retornar `NOT_RECONCILED_STATE_CHANGED` quando perdeu a corrida.
Não ativar provider, nem liberar reenvio externo real.

## Limite crítico de segurança

`authoritative_absence=True` vindo de um adapter injetado **não é**
um certificado de `NO_EFFECT_FENCED` emitido por autoridade
independente. Mesmo com o CAS local, essa declaração permanece
não confiável para habilitar SEND externo em produção. O efeito de
um pagamento, mensagem ou ordem pode já ter acontecido se a resposta
perdeu-se. Este laboratório não homologa HUMAN_OWNER externo,
autorização original semântica CAS, custódia monotônica contra rollback,
recibo causal do provedor, nem SQLite nativo resistente a restauração.

**Regras:** UNCERTAIN=ZERO_AUTO_RESEND, 0/6 P0, HARD NO-GO,
Negócios congelado, sem merge/deploy, Worker, trade, credencial,
custo novo ou conta AWS. A partir de 06/11 qualquer despesa
exigirá autorização expressa.
