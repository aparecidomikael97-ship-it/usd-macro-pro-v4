# AtlasQuant / AION — M67: preparação de teste com imports originais A118

**19/10/2026 · GO-LAB de preparação · NO-GO integração · HARD NO-GO operação.** Este checkpoint é documento de continuidade em branch separada. NÃO é prova de teste de produto executado no M67.

## Estado da fonte e do ambiente
- PR A118 [#1326](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1326) segue aberto/Draft, sem merge, HEAD fixado `c62fab663c6349d7320f7843c8d09587c514426b`.
- Computador am12 ficou **OFFLINE**. O contêiner da conversa não tinha um checkout A118 com todas as dependências e não conseguiu obter um arquivo ZIP completo do repositório pela rede. **Não tentamos simular matrícula de produtor ou ativação**.
- Novo arquivo `test_m67_original_a118_negative.py`: escrito em ambiente isolado, importa os módulos **originais** e fixtures do teste real quando executado dentro de um checkout A118 válido. Verificação de sintaxe **OK**, mas **não houve import nem teste de integração real**. `0` testes originais executados no M67.
- SHA-256 do arquivo de teste: `176647766e4386fcfd9ca7e90f0a2ae92e49facf6155cb8b08c971072bcfb7e0`.

## Os dois testes preparados, não executados

**N-M67-01 — plano bloqueado sem autoridade independente.** Usa a fixture oficial `_post_incident_runtime`, `_safe_reconciled_snapshot`, `_readiness`, `_safe_flag` e `_access` da suíte histórica. Mesmo que o gate diagnóstico esteja READY, `prepare_global_worker_activation_plan` deve devolver `BLOCKED` / `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`, sem `plan`, sem `approval`, sem mutação da flag nem execução do Worker.

**N-M67-02 — reabertura bloqueia gate.** Usa a fixture oficial para uma observação posterior a fechamento durável e chama `reconcile_global_worker_incident_center`, `assess_post_incident_reactivation_gate` e `validate_reactivation_gate_for_execution`. Deve retornar `BLOCKED`; o parâmetro `approval` é um dicionário mínimo apresentado **somente ao validador negativo**, jamais ticket oficial ou autorização de ativação. Nenhuma chamada de `activate_global_worker_feature_flag` ou provider.

Os testes não alteram arquivos de produto. Caso falhem por dependências ou pela fixture, registrar o erro e não reescrever o guard para fazer passar.

## Evidência CI oficial anterior — não nova

[Workflow A118 dirigido, run 38919546556](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38919546556): **39 testes OK Windows e 39 OK Ubuntu**, código e dependências originais, mas focados em Outbox/claim/producer e **não equivalentes** a N-M67-01/02.

[Workflow Quality/Security, run 38919546692](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38919546692): Security **365 PASS**; Quality **6562 total, 50 FAIL + 34 ERROR**, incluindo **três resultados históricos de reativação (1 FAIL + 2 ERROR)**. A falha KeyError `plan` é explicada pela negação obrigatória de emitir plano sem autoridade independente. Não remover nem transformar os legados em xfail.

### Fonte rastreada
- `test_atlasquant_aion_global_worker_reactivation_gate.py` Git blob `6c66e11b4c29b2bef1ff277a0c47740cdb0bf220`.
- `atlasquant_aion_global_worker_activation.py` Git blob `df43bb4371c784396069f4ede51205b0aa19cc0a`.
- `atlasquant_aion_global_worker_reactivation_gate.py` Git blob `8412ada82761de37a72a8f29af7f8672cfb5b082`.
- `atlasquant_aion_global_worker_incident_reconciliation.py` Git blob `85541bb2d10f0b97b096df10b5184851160cfec9`.

## Pacote temporário de conversa

`ATLASQUANT_AION_M67_PREPARACAO_TESTE_ORIGINAL_20261019_VERIFICADO.zip` contém **3 arquivos** (checkpoint completo, teste pendente e manifesto), com CRC/sha dos membros conferidos.
- SHA-256 do ZIP: `d1edc741406195ebf6c5e25cf5add0f9056fe11787f459ef8026b6f47d7c76d1`.
- **O ZIP não foi copiado no Windows offline e não foi armazenado integralmente no GitHub.** Apenas este checkpoint textual está na branch pública.

## Próxima execução quando houver checkout real

Com o Windows conectado ou uma cópia pinada offline com dependências instaladas:
1. Confirmar commit exato e hashes de arquivos oficiais.
2. Copiar **somente** `test_m67_original_a118_negative.py` para LAB fora da árvore de produto e garantir que esteja importável com `PYTHONPATH`. Rodar com working directory na raiz A118 e `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v test_m67_original_a118_negative`.
3. Guardar log, hash dos resultados e classificar erro de import/fixture versus falha real de negação. Não iniciar Worker, flag, provider, merge ou deploy.
4. Revisão independente antes de integração; três REDs históricos permanecem.

**Estado:** 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND, 0 testes A118 originais executados no M67, sem gasto ou deploy. HARD NO-GO preservado.
