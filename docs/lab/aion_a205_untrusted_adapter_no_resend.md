# AION A205 — declarações do adapter não são prova de ausência de efeito (LAB)

**28/10/2026 UTC · Draft · 0/6 P0 homologadas · HARD NO-GO**

## Hipótese de segurança verificável

Após a chamada `adapter.send` (possível efeito irreversível), o Outbox:
1. pode colocar o registro em `RETRY` quando recebe `accepted=False, retryable=True`, mesmo sem comprovar que nada foi executado;
2. pode transformar `UNCERTAIN` ou `SENT` em `RETRY` quando `adapter.reconcile` retorna `found=False, authoritative_absence=True`.

Ambas são declarações do **próprio adapter injetado**, não um atestado independente de `NO_EFFECT_FENCED`. Um falso negativo, um ACK perdido após o efeito ou um adapter enganoso podem liberar nova tentativa, apesar das proteções de concorrência A202–A204.

## Método RED-first

`labs/test_a205_unverified_adapter_absence_no_resend.py` usa o SQLite real, um mock de efeito não idempotente e um adapter local que mente deliberadamente. Testa resposta incerta após efeito; rejeição chamada `retryable` após executar efeito; rejeição chamada definitiva após executar efeito; confirmação sintética; ausência alegada em `SENT`. Não contata provedores, não utiliza chaves ou contas de clientes.

**Primeiro observar CI RED**: se a implementação antiga realmente liberar `RETRY`, registrar os logs nos dois SOs. Depois corrigir *fail closed* mantendo `UNCERTAIN` e sem reenvio automático. Atualizar os testes legados que esperavam `RETRY` de declarações autoatestadas **somente com migração explícita documentada**, sem `skip`/`xfail`. Preservar evidência histórica RED. Reexecutar suite dedicada e Quality geral.

## Limites

Esta contenção não é autenticação de recibos e não cria autorização real de envio. Não satisfaz raiz HUMAN_OWNER original externa, admissão da intenção semântica, custódia monotônica independente resistente a rollback, recibo H0 causal e `NO_EFFECT_FENCED` verificável ou provas nativas SQLite same-inode.

`UNCERTAIN=ZERO_AUTO_RESEND`, seis P0 externas 0/6 homologadas, HARD NO-GO. Proibidos Worker, provider SEND real, pagamentos, ordens, merge, deploy e novas despesas. Negócios permanece congelado.
