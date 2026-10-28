# AION A206 — callback SEND atrasado não pode rebaixar efeito CONFIRMED (LAB)

**28/10/2026 UTC · Draft RED-first · 0/6 P0 homologadas · HARD NO-GO**

## Hipótese

A205 garante que `accepted=False` ou alegação de ausência não abra `RETRY`.
Ainda há uma janela temporal entre a transição local `CLAIMED → UNCERTAIN`
e o retorno da chamada `adapter.send`: enquanto o callback está bloqueado,
outra conexão SQLite pode reconciliar o mesmo efeito e registrar `CONFIRMED`.
Se o callback antigo retorna timeout ou `accepted=True,confirmed=False`,
os ramos de pós-SEND fazem UPDATE sem comparar estado/lease/snapshot.
Uma resposta atrasada poderia mudar `CONFIRMED → UNCERTAIN` ou
`CONFIRMED → SENT` e produzir desacordo com o ledger de efeitos.

## Prova RED-first

`labs/test_a206_outbox_late_send_reply_cas.py` usa duas conexões SQLite WAL
em threads separadas, `threading.Event` para controlar a ordem, efeito
somente sintético e uma confirmação de reconciliação falsa/propositalmente
local. Exige que `CONFIRMED` não seja sobrescrito e que o ledger permaneça
consistente. Primeiro registrar CI RED real em Ubuntu/Windows. Somente depois
de confirmar o defeito, fazer CAS condicionado ao snapshot original de
despacho nos ramos posteriores a `adapter.send`, preservando A202–A205.
Sem `skip`, `xfail`, silenciar erros ou chamar provedores reais.

## Fronteiras de segurança

O teste não prova recibo H0 real, HUMAN_OWNER externo, intenção original
imutável, custódia monotônica antirollback nem proteção nativa de SQLite.
Proibidos Worker, SEND real, trading, pagamento, AWS/KMS, novas despesas,
merge e deploy. Negócios permanece congelado. `UNCERTAIN=ZERO_AUTO_RESEND`;
**0/6 P0 externas homologadas, HARD NO-GO**.
