# AION A206 — resultado atrasado de SEND não pode apagar CONFIRMED (LAB)

**28/10/2026 UTC · RED-first · DRAFT · 0/6 P0 homologadas · HARD NO-GO**

## Janela de concorrência suspeita

A205 negou reenvio diante de ausência/rejeição autoatestada, porém dois
outros caminhos de `ExecutionOutbox.dispatch_claimed` continuam usando
`UPDATE action_outbox ... WHERE idempotency_key=?` sem CAS de estado:
- exceção/timeout depois do efeito → grava `UNCERTAIN`;
- aceito mas ainda não confirmado → grava `SENT`.

Enquanto o callback `adapter.send` aguarda resposta, uma segunda
conexão SQLite pode executar `reconcile` e gravar `CONFIRMED` para a
mesma intenção. O resultado antigo do primeiro adapter não deve rebaixar
esse registro mais recente para `UNCERTAIN` ou `SENT`.

## Prova reproduzível (sem serviço externo)

`labs/test_a206_late_send_outcome_cas.py` usa SQLite WAL real em duas
conexões abertas em suas threads respectivas; um adapter falso registra
um efeito sintético, para dentro de `send` com `Event`, enquanto a
conexão principal confirma o resultado. Então o teste libera o callback
antigo, alternando:
1. `TimeoutError` de ACK perdido;
2. resposta `accepted=True, confirmed=False`.

Requisito: `CONFIRMED` e ledger preservados, uma única tentativa, nenhum
reenvio, resposta local `NOT_DISPATCHED_STATE_CHANGED`. Controles sem
reconciliação simultânea devem continuar gerando `UNCERTAIN` e `SENT`
respectivamente.

**RED primeiro**, em Ubuntu e Windows, para separar defeito real de erro
de fixture; somente depois adicionar CAS por estado/lease/timestamp,
conferir `rowcount==1` e rodar suites A202–A205, Quality e Security.
Nenhum teste usa provedor, credenciais, token real ou rede.

## Governança

Este patch, quando testado, protege um registro SQLite local; não prova
a existência do efeito no provedor, recibo causal, identidade original
HUMAN_OWNER independente, intenção semântica sem duplicações, custódia
monotônica antirollback, NO_EFFECT_FENCED ou SQLite nativo íntegro.
Nenhum resultado pode converter P0 sem aceitação independente.
`UNCERTAIN=ZERO_AUTO_RESEND`; **0/6 P0; HARD NO-GO**. Sem Worker, trading,
merge, deploy, AWS, contratação, envio real ou alteração em Negócios.
