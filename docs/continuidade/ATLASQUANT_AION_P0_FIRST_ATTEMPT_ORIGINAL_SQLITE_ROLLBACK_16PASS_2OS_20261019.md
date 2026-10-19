# ATLASQUANT / AION — P0 primeira tentativa + SQLite crash/restauração, 16 testes PASS por SO

**Data:** 19/10/2026. **Veredito:** comprovação de comportamento e lacuna do Outbox original sob rollback do próprio SQLite. **NÃO É CORREÇÃO NEM HOMOLOGAÇÃO.** Estado: 0/6 P0 homologados, Worker OFF, HARD NO-GO, ZERO_AUTO_RESEND, sem merge/deploy/novos gastos.

## Rastreabilidade verificável
- Original A118 commit `c62fab663c6349d7320f7843c8d09587c514426b`.
- Branch isolada `lab/aion-p0-first-attempt-sqlite-crash-rollback-20261019`.
- Novo teste `test_aion_p0_first_attempt_sqlite_crash_rollback_lab.py` commit inicial `d518a8183dc0e1da93827418d7bc2dd1c1abb112`; correção de encerramento de conexão no teste `2bbd073fdf4454788bc096dfc02a676e82ed8456`.
- Workflow `.github/workflows/aion-p0-first-attempt-crash-rollback-lab.yml` commit `d8e1f567580f8a49d63293a99b77e77ab44f231e`, permission `contents:read` e matriz Ubuntu/Windows.
- Contexto técnico `docs/aion/AION_P0_FIRST_ATTEMPT_ORIGINAL_SQLITE_PROCESS_CRASH_ROLLBACK_20261019.md` commit `55661324c9f32a0476e4fbe13f634740ea3fddb6`.
- GitHub Actions inicial [#39311800296](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39311800296): Ubuntu 16/16 PASS, Windows 2 ERROR por falha do fixture `with sqlite3.connect` que NÃO fechava a conexão em teardown (`WinError 32`). Erro exclusivo do teste, não do produto. **Não apagar RED histórico.**
- CI corrigida [#39312063253](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39312063253): **COMPLETED SUCCESS**, Ubuntu job `118263937850`: 10/10 novos + 4/4 A110 originais + 2/2 A83 originais = **16/16 PASS**; Windows job `118263937369`: mesmos 10+4+2 = **16/16 PASS**. **16 cenários distintos e 32 execuções aprovadas.**
- Original Outbox `atlasquant_aion_execution_outbox.py` blob `6bad4ee9ba5909bbb49c609a5d3ac3c05c16ab83`; teste A110 `2ca086e315ee629026968924bae8e64cafd3a1f1`. Ambos HASH CONFIRMADO no CI, permanecem inalterados.

## Casos com significado técnico objetivo
1. `enqueue` original realmente persiste decisão e intenção vinculadas em SQLite, reabertas após encerramento.
2. Commit de **transição sintética** a `UNCERTAIN` seguido de `os._exit(73)` retorna `UNCERTAIN` na reabertura, sem claim ou retry após vencimento de lease.
3. Morte do subprocesso *antes* do COMMIT reverte atualização de fixture `UNCERTAIN` e deixa `CLAIMED` anterior; lease pré-dispatch sem qualquer contato de fornecedor pode reciclar localmente. Não extrapolar para effect-before-commit real: a fronteira produtiva é NO-GO.
4. `SENT`/marcadores possíveis de efeito não voltam automaticamente ao claim após reinício, `reconcile` original nega antes de acessar propriedades de um adapter, outros tenants não leem/chamam o claim.
5. `dispatch_claimed` original **mantém o hard stop** `INDEPENDENT_PRODUCER_NOT_ENROLLED`, sem sequer inspecionar `adapter.send`.
6. **LACUNA REAL DE ANTIROLLBACK LOCAL (teste 09):** backup SQLite gerado ANTES de o teste gravar `UNCERTAIN`, transição marcada/commit/crash/reabertura confirmando `UNCERTAIN`. Restauração do backup anterior (somente diretório temporário) apaga marcador: reabre em `PENDING` e `claim_next` retorna `CLAIMED`. Não há high-water independente do mesmo backup que detecte tal retrocesso. O hard stop produtor ainda impede efeitos externos, portanto não foi demonstrado bypass de envio. O **TESTE PASS indica reprodução bem-sucedida da lacuna, não ausência de lacuna**.

## Limites da evidência
- Crash simulado com `os._exit` não é corte de energia, `fsync` real, corrupção física, SSD, reboot de máquina, perda de journaling, ou validação do Windows Hello/TPM. O resultado do Windows é runner CI, não máquina real do proprietário.
- A transição `UNCERTAIN` e restauração de backup são escritas **SQL diretas de fixture** em arquivo temporário. Não demonstram uma chamada externa efetiva, envio, semântica de fornecedor, nem o percurso produtivo do dispatcher (bloqueado).
- Os testes não fecham nenhum dos seis P0 nem corrigem os dois SQLite P0 históricos; Quality/Security integrais e auditoria externa não foram executados nesta rodada.
- `try/finally db.close()` resolve o erro do TESTE Windows. Isso não comprova correção dos erros históricos SQLite do AION.

## Próxima frente priorizada
**P0 antirollback H0:** definir e implementar separadamente, em laboratório não autorizante, fonte de high-water de primeiro intento em custódia realmente fora do domínio de restauração do SQLite e Worker. Fixar identidade do custodiador, epoch/sequence/cabeçalho de witness, digest de operação, nonce durável consumível uma única vez, revogação/rotatividade e barreira CAS antes do primeiro efeito; indisponível/fork/replay/restauração antiga => BLOCKED. Um JSON do mesmo host, um hash auto-gerado e cópia local do banco NÃO satisfazem custódia independente.

Até existir custodiador escolhido e evidência real, próxima etapa viável é **auditar os dois P0 originais de compatibilidade SQLite e concorrência**, sem relaxar fonte de prova nem lançar novos serviços. Não habilitar adapter/Worker ou reenvio.

**Status conclusivo: AION HARD NO-GO; 0/6 P0; nenhum merge/deploy, nenhum gasto e nenhuma operação externa.**
