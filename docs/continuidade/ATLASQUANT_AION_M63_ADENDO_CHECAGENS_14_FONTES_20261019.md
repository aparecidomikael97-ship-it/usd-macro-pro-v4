# AtlasQuant / AION — M63: adendo de checagem de fontes e ensaio alternativo

**2026-10-19 · complemento documental na branch de checkpoints. HARD NO-GO, Worker desligado, NO-GO integração, 0/6 P0 homologados.**

Este adendo **NÃO substitui** o [checkpoint principal M63](ATLASQUANT_AION_M63_TESTES_NEGATIVOS_ORIGEM_20261019.md). Ele preserva uma segunda verificação isolada realizada na mesma rodada com *casos diferentes*. O código A118 do produto não foi modificado.

## Fontes oficiais lidas em GitHub

HEAD do PR Draft #1326: `c62fab663c6349d7320f7843c8d09587c514426b`, sem merge na consulta. **14/14 checagens ESTÁTICAS de estrutura de código** confirmadas em seis arquivos; não são testes de execução do A118:

| Arquivo | Git blob SHA-1 |
|---|---|
| `atlasquant_aion_global_worker_supervision.py` | `8a6ab6be8789deeeb80b6b2df39df9745d91e902` |
| `atlasquant_aion_global_worker_incident_reconciliation.py` | `85541bb2d10f0b97b096df10b5184851160cfec9` |
| `atlasquant_aion_global_worker_live_verification.py` | `3cfd1926aac5b3768595cb3ffdfad6fed539490b` |
| `atlasquant_aion_global_worker_activation.py` | `df43bb4371c784396069f4ede51205b0aa19cc0a` |
| `atlasquant_aion_unified_journal.py` | `8fe4b1d74e90405dadb41f63941a778d0ba85d51` |
| `atlasquant_aion_global_worker_reactivation_gate.py` | `8412ada82761de37a72a8f29af7f8672cfb5b082` |

Os 14 itens observam o retorno `NO_INCIDENT`, ID por digest truncado, rótulos literais de origem/`CONFIRMED`, proposta `OPEN` sem efeito, ausência de autenticação de produtor **na função de proposta**, supervisor derivado do mapa recebido, reconciler com base/proposta e ledger de **fechamentos**, exigência de flag ENABLED no verificador LIVE, negação independente de ativação, ausência de eventos GW OPEN/REOPEN no EVENT_TYPES do journal consultado, e exigência de gate ligada ao ledger de closures. **Nada disso certifica autoridade, completude ou persistência de OPEN.**

## Dois ensaios isolados — distintos; não somar como homologação

**Ensaio principal documentado no checkpoint M63:** 9 casos sobre um excerto da função `operational_incident`, 6 PASS / 3 FAIL deliberadamente futuros. Os três FAIL pedem tratamento explícito de origem sem matrícula, `incident_open` não booleano e digest ausente. São especificações futuras da **camada de admissão**, não prova de vulnerabilidade operacional da função read-only.

**Segundo ensaio deste adendo:** 8 casos sobre a cópia M61 da mesma função, **6 PASS / 2 FAIL deliberadamente futuros**. Os seis PASS caracterizam os rótulos atuais e a ausência de execução externa. Os dois FAIL esperam **campos futuros, ainda não aprovados**: `source_auth_state=UNVERIFIED` e `admission_state=NOT_ADMITTED`. A função não possui esses campos, mas **não é contratada para admitir incidentes**.

Nenhuma das duas suítes importou o núcleo A118 completo, reexecutou CI oficial ou proveu produtor autenticado. A revisão Codex/externa permaneceu pendente.

## Pacotes preservados separadamente nesta conversa

- `ATLASQUANT_AION_M63_TESTES_NEGATIVOS_ORIGEM_20261019_VERIFICADO.zip` — primeira suíte, 8 membros, SHA-256 `f769447de5b093886dafe326addaca32986401b72975c3b5713e3c78a8554b44`.
- `ATLASQUANT_AION_M63_CONTRATO_ORIGEM_20261019_VERIFICADO.zip` — segunda suíte + matriz + checagens estáticas, 9 membros, SHA-256 `0e3cf463ecc9b60459987ad56f5659c56e4c64b14c9b98116b0b7f344b1d4f69`.

Ambos os ZIPs passaram em CRC local. **Os binários não foram enviados para o GitHub, nem copiados no Windows offline.** Os links de download permanecem na conversa.

## Próxima decisão, não apenas próxima contagem de testes

Atribuir legitimamente **quem autentica a fonte de uma observação** e **quem aceita/persiste um OPEN/REOPEN**, com vínculo causal, escopo, revisão e recuperação sob flag DISABLED. Sem este contrato de autoridade, adicionar rótulos positivos ou gravar propostas num journal genérico não resolve o P0.

**Sem merge, deploy, Worker, gastos novos ou P0 encerrado.** Os três REDs históricos de reativação e a Quality A118 histórica 50 FAIL/34 ERROR permanecem pendentes, sem reexecução nesta etapa.
