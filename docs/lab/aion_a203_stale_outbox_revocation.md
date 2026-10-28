# AION A203 — revogação local atrasada versus efeito confirmado (LAB / RED-first)

**27/10/2026 — HARD NO-GO, 0/6 P0 homologadas, UNCERTAIN=ZERO_AUTO_RESEND.**

Na branch A202, `ExecutionOutbox._set_blocked` atualiza a linha
`action_outbox` para `REVOKED` ou `BLOCKED_REAPPROVAL` sem incluir
uma condição SQL sobre o estado/lease observado pela chamada. Isso pode
sobrescrever `UNCERTAIN`, `SENT` ou até `CONFIRMED` depois que outra
chamada de dispatch atingiu o efeito. A auditoria A203 procura comprovar
esse cenário com duas conexões SQLite independentes e cronologia forçada.

`labs/test_a203_outbox_stale_revocation_cas.py` cria uma intenção
`CLAIMED` com um identificador de Worker idêntico nos dois dispatches.
A segunda thread lê a intenção antiga, entra na revalidação local e espera
um Event. Enquanto ela espera, a primeira conexão (a) confirma um efeito
sintético, ou (b) registra `UNCERTAIN` após Timeout sintético já com
efeito registrado no adapter. Só então o evento libera a revalidação
antiga, que responde `allowed=False`. Resultado correto: ela **não pode
reescrever** o efeito mais recente como `REVOKED`; revogação de uma
intenção ainda `CLAIMED` deve continuar bloqueando antes de SEND.

Não usa rede, credenciais reais ou provider. Primeiro observar o RED
no CI. Se real, aplicar CAS com estado/lease esperados nos fluxos de
dispatch e retorno fail-closed, sem criar retry ou limpar `UNCERTAIN`.
A correção local não autentica HUMAN_OWNER nem prova custódia externa
antirollback, primeira intenção semântica ou receipt do provider real.

Negócios congelado; sem custo, AWS, Worker, envio, trading, merge, deploy.
