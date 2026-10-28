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

## Reprodutibilidade RED e correção GREEN (provas GitHub Actions)

**RED verdadeiro antes da correção:** [A203 run #40606826916](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40606826916) executou 9 testes em cada sistema. Em ambos, os dois novos cenários falharam precisamente com `A203_STALE_REVOCATION_OVERWROTE_EXTERNAL_EFFECT_STATE_RED`, e os demais passaram. No cenário de confirmação antiga, estado armazenado `REVOKED` ao invés de `CONFIRMED`; no cenário de ACK incerto, `REVOKED` ao invés de `UNCERTAIN`. Fake adapter local registra exatamente um efeito em ambos, nunca rede real. O erro foi reproduzido com conexões SQLite independentes.

**Correção:** `ExecutionOutbox._set_blocked` agora recebe a fotografia da intenção `observed=intent`, incluindo `state`, `lease_owner` e `lease_until`. O `UPDATE` só altera o banco quando os três valores correspondem ao estado atual. Se outra chamada já avançou para `UNCERTAIN`, `SENT`, `CONFIRMED` ou houve troca de lease, a revogação atrasada não altera o registro nem permite novo SEND. Todos os sete call sites internos de bloqueio/reconciliação passam a fotografia. A reconciliação não declara `REVOKED` se perdeu a corrida: usa `NOT_RECONCILED_STATE_CHANGED`.

**GREEN confirmado:** [A203 run #40607042945](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40607042945), **9/9 PASS Ubuntu e 9/9 PASS Windows**, incluindo três testes A203 e três A202 por SO mais três do runner por descoberta? O runner efetivamente executou nove métodos em cada sistema (os métodos A202 incluem três e os A203 incluem três; a duplicação de importação da classe base em `labs/test_a203...` executa os três A202 também). Logs brutos inspecionados.

Essas verificações não provam testemunho original independente, rollback externo nem receipt causal de provedor. A função de reconciliação continua a depender de declaração do adapter para `authoritative_absence`; não interpretar tal declaração sintética como comprovação H0. A suite Quality/Browser e gates de segurança ainda precisam ser confirmados no HEAD final.
A correção local não autentica HUMAN_OWNER nem prova custódia externa
antirollback, primeira intenção semântica ou receipt do provider real.

Negócios congelado; sem custo, AWS, Worker, envio, trading, merge, deploy.
