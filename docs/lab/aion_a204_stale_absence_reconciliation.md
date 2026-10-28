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

## Evidência RED → correção → GREEN

**RED antes de alterar o código:** [workflow A204 #40609186532](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40609186532) apresentou **duas falhas reproduzidas no Ubuntu e duas no Windows**, `A204_STALE_ABSENCE_REOPENED_CONFIRMED_INTENT_RED`. Em ambas as situações iniciais (`UNCERTAIN` e `SENT`), a resposta negativa atrasada transformou um registro já `CONFIRMED` em `RETRY`. Foram usados dois SQLiteChatStore independentes e uma chamada sintética ao adapter, nenhuma rede.

**Correção A204:** a transição para `RETRY` em `ExecutionOutbox.reconcile` agora usa um UPDATE CAS com `state`, `attempts`, `lease_owner`, `lease_until`, `dispatch_started_at`, `sent_at`, `confirmed_at` e `effect_ref` da fotografia original, além de chave e escopo. Exige `cursor.rowcount == 1`; o perdedor retorna `NOT_RECONCILED_STATE_CHANGED` com estado atualizado, sem abrir retry. Os demais fluxos de reconciliação não foram habilitados.

**GREEN após correção:** [workflow A204 #40609299404](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40609299404), **9/9 PASS Ubuntu e 9/9 PASS Windows**, logs de jobs inspecionados. São 3 testes A204, 3 de regressão A203 e 3 A202 em cada sistema. O caso sintético de ausência não concorrente continua retornando RETRY, mas **não constitui atestado real de ausência de efeito**. A bateria geral Quality, browser e Core Security no HEAD final ainda precisa ser observada antes de anunciar sucesso completo.

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
