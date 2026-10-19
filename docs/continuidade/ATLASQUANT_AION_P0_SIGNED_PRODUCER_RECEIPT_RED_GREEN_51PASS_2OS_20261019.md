# AtlasQuant / AION — P0 AUTENTICIDADE DE RECIBOS — assinatura de produtor (LAB) — 19/10/2026

**VEREDITO:** GO-LAB *limitado* para contrato de assinatura matemática Ed25519 de recibos sintéticos; NO-GO para produção, homologação, reenvio, reconciliação operacional e Worker. **0/6 P0 homologados, HARD NO-GO.**

## Origem e isolamento
- A118 original pinado no commit `c62fab663c6349d7320f7843c8d09587c514426b`.
- Branch LAB `lab/aion-p0-producer-receipt-signature-20261019`.
- Arquivo novo `atlasquant_aion_p0_signed_producer_receipt_lab.py` commit inicial `01126f862d32bc41955de0d3e02723ac7a4d6481`, aprimoramento de escopo `7cb2acd0e65b6ce30aef26ad5d86e85d652df033` e correção efetiva `dd456083c23669c1e84ed54a0945aae06d61a879`.
- Testes novos `test_atlasquant_aion_p0_signed_producer_receipt_lab.py` commit `e08e454dcd866bbc94cd6bbc5809d516c0b35901` (32 casos distintos).
- Workflow `.github/workflows/aion-p0-signed-producer-receipt-lab.yml` commit `c18b0767a3002b72262cc12c78525e5c35b93d5a`.
- Análise de limites `docs/aion/AION_P0_PRODUCER_SIGNED_RECEIPT_BOUNDARY_LAB_20261019.md` commit `32accc4a9d09c189609b62b8271d0eb0d1170bce`. É documento apenas, não integrado.

## RED real encontrado e corrigido em LAB
- CI inicial [#39309280345](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39309280345) **FAIL** no novo protótipo. Testes `test_15_wrong_issuer_key_version` e `test_16_wrong_issuer_key_id` detectaram que assinatura correta sob a chave injetada não era ligada aos campos `producer_key_id` e `producer_key_version` assinados. O verificador devolvia `P0_CRYPTO_CONSISTENT_EXTERNAL_EFFECT_UNVERIFIED` quando deveria devolver `P0_ISSUER_PIN_MISMATCH`. Nenhum código A118 original era a causa.
- Fix em LAB `dd456083c23669c1e84ed54a0945aae06d61a879`: compara ID e versão assinados ao registro de chave injetado; testes negativos mantidos, sem afrouxar assertions.
- CI pós-correção [#39309509077](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39309509077) **COMPLETE SUCCESS**, Ubuntu job `118255141157` e Windows job `118255140822`. Ambos:
  - `A118_RECEIPT_SOURCE_4_BLOBS_MATCH` (quatro arquivos originais preservados).
  - Descoberta `P0_RECEIPT_32_CASES`.
  - **32/32 PASS** novos P0, **11/11 PASS** controles A37+A83, **8/8 PASS** B2B real-receipt design-only; **51/51 PASS em cada SO**, 102 execuções de casos.
- Estas 102 execuções **não** substituem Quality/Security integrais, provas reais de fornecedor ou fechamento de P0.

## O que foi demonstrado
- Assinatura Ed25519 sob um registro de emissor público **injetado no laboratório** é matematicamente verificada sobre recibos canônicos separados por domínio e com campos exatos. Hash de intenção, owner/tenant/workspace, host, conta, key ID/version, action class, idempotency, attempt, epoch, nonce, receipt, head/sequence e janela estão assinados/comparados.
- `POSITIVE_COMMITTED` e `NEGATIVE_NO_EFFECT_FENCED` exigem domínios/tipos assinados distintos. Modificação posterior de tipo/referência é detectada pela assinatura. Um status `OUTCOME_UNKNOWN` ou `FAILED` local não vira comprovante terminal.
- Mesmo recibos com assinatura criptograficamente correta ficam `state=BLOCKED`, `issuer_authenticated=False`, `independent_witness_verified=False`, `producer_effect_confirmed=False`, `producer_no_effect_fence_confirmed=False`, `receipt_admitted=False`, `unknown_outcome_cleared=False`, `automatic_retry_allowed=False`, `saga_advance_authorized=False`, `writer_called=False`, `external_action_executed=False`.
- As entradas de fonte de chave, escopo esperado, head, sequência anterior e recibos usados são **sintéticas e fornecidas pelo mesmo ensaio**, não ancoradas fora do Worker/aplicação e não mantidas em custódia durável independente. Não foi feito contato real com provedor nem havia assinatura do fornecedor.

## Pontos pendentes de verificação e próxima prioridade
1. **Realidade do emissor**: definir conta/provedor e enrollment da chave pública fora do controle do executor, vincular issuer ID, conta, host, tenant, key version e revogação a custódia independente; um arquivo JSON criado pelo próprio produtor NÃO basta.
2. **Prova POSITIVA**: confirmação atual do efeito pelo sistema externo, consulta/readback autenticados e proteção contra replay/rollback, com evidência de commit real e escopo exato. Assinatura matematicamente válida não implica execução.
3. **Prova NEGATIVA**: fence *garantido pelo próprio fornecedor* contra efeito atrasado, enfileirado ou já emitido. Ausência em listagem, timeout e recibo `FAILED` local NÃO autorizam retry.
4. **Anti-replay**: nonces/epoch/head de testemunha independente com high-water durável atômico e rechecagem antes de qualquer decisão/escrita. Fazer testes de crash/restauração, concorrência e contexto trocado.
5. **Teste real de provider**: só com autorização explícita e aprovação do custo/privacidade, se aplicável; sem gastar, planejar protocolo e checar documentação do fornecedor. Preservar ZERO_AUTO_RESEND.
6. **CI integral Quality/Security** e auditoria externa para qualquer integração. RED M71 e cinco outros P0 continuam pendentes.

## Estado e restrições
Não houve ativação de Worker, reenvio, merge, deploy, escrita externa, conta, gasto, cliente real, credencial produtiva ou ação de fornecedor. Os controles A37 originais continuam deny-only. Nenhum dos seis P0 foi homologado: **0/6, HARD NO-GO**.
