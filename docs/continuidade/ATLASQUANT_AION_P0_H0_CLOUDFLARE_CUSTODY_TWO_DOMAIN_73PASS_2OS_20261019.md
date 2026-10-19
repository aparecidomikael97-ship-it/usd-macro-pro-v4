# Checkpoint Mestre — AION P0 H0: Cloudflare Durable Objects, contrato de custódia em dois domínios e rollback

**19/10/2026 — VEREDITO: GO-LAB SOMENTE PARA PROTOCOLO SIMULADO.** Continua **0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND**. Nenhum merge/deploy, instalação de Cloudflare, conta, credencial, ação externa, mensagem, pagamento ou novo gasto.

## Retomada e objetivo

Diagnóstico H0 de SQLite real já mostrou que restauração manual pode fazer `UNCERTAIN` voltar para `PENDING` sem que um exame local detecte a perda. Na rodada anterior 40/40 testes por SO comprovaram conservação estrutural dos gates A118 em Worker, Outbox, restore e H0, **mas não** uma testemunha externa. A presente rodada investigou Cloudflare Durable Objects para permitir futura guarda monotônica e criou um **modelo offline com dois arquivos SQLite locais** que demonstra a fronteira real: *se o suposto custodiante também retrocede, não existe prova independente*.

## Fatos sobre Cloudflare (documentação oficial, consultada nesta rodada)
- SQLite-backed Durable Objects tem armazenamento fortemente consistente e transacional; `ctx.storage.transactionSync(callback)` dá transação síncrona para leituras/atualização de CAS. Não usar `sql.exec("BEGIN TRANSACTION")` nem `SAVEPOINT` para iniciar transações da API SQL. https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- No Workers Free, SQLite Durable Objects suporta até 5 GB de dados totais por conta; limites de uso incluem 5 milhões de linhas lidas e 100 mil linhas escritas/dia; extrapolar um limite do Free faz falhar operações desse tipo, sem garantir capacidade infinita. https://developers.cloudflare.com/durable-objects/platform/pricing/ e https://developers.cloudflare.com/durable-objects/platform/limits/
- **Risco crítico**: a mesma API de DO SQLite oferece Point in Time Recovery para restaurar conteúdo anterior dentro dos últimos 30 dias. Isso ajuda recuperação, mas um admin capaz de restaurar PITR/deletar/mudar código também pode retroceder a sequência que deveria provar monotonicidade. https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Operações SQL síncronas têm fronteira de execução que não cede entre awaits, mas `await` no meio de reserva pode abrir interleaving; consumidor de cursor assíncrono precisa finalizar leitura antes de yield. https://developers.cloudflare.com/durable-objects/api/state/

## Artefatos e commits no repositório
- Branch LAB isolada: `lab/aion-p0-h0-cloudflare-custody-contract-20261019`, baseada no checkpoint de avaliação anterior `40b1d27827ca1840b37c67437d1d76f37630f7bf`.
- `atlasquant_aion_p0_h0_custody_two_domain_model_lab.py`, commit `a68963fb0b5a2a05ed23e69b896d77d197ae3974`: **modelo SQLite local** com `BEGIN IMMEDIATE` para serializar reservas sintéticas, CAS de sequência por escopo, nonce/intent únicos, rejeição após resposta perdida e comparação de head local versus custódia modelada. Não contém Cloudflare API, chaves, signing, rede, verificação de identidade ou contas. **Cada retorno é `state=BLOCKED`, todas as flags de autoridade/trust/reenvio/external action são `False`**, mesmo em `MODEL_RESERVED_NOT_AUTHORITY`.
- `test_aion_p0_h0_custody_two_domain_model_lab.py`, 20 casos, commit inicial `6471436b835fb4c9368318158fea4e57066c52fb` e correção de assert de teste `ef20571075443bf3bca3b65d3b30ca215a33beab`. Casos: duas threads disputando CAS, repetição de intent, nonce, timeout pós-commit, epoch/sequence, input inválido, fechamento/retomada, rollback manual executor-only, custody-only e **ambos**.
- `docs/aion/AION_P0_H0_CLOUDFLARE_DO_CUSTODY_GATE_PROPOSAL_20261019.md`, commit `c6a16351df122cee70acf7815878697b238f94ad`, apresenta requisitos concretos, custo/quotas, `transactionSync`, custódia IAM, riscos PITR e checklist antes de qualquer implementação.
- `.github/workflows/aion-p0-h0-cloudflare-custody-contract-lab.yml`, commit `4d03ff6d42b0cf246887f6045a8ff6bba145ed72`: matriz Ubuntu+Windows, readonly `contents:read`, pinos SHA do observador H0/Worker/Outbox originais, 20 novos + 53 regressões históricas.
- O primeiro workflow [#39326585196](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39326585196) e a execução seguinte [#39326796667](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39326796667) falharam por **quatro erros em uma ASSERT de teste** que usava `assertNotIn("READY", str(result))` e capturava `ALREADY_RESERVED` (que é mensagem de bloqueio, NÃO autorização). Alterou-se apenas o teste para verificar o campo `state!="READY"`, `first_effect_allowed=false` e `automatic_retry_allowed=false`, sem modificar o simulador/segurança. Não classificar essas falhas como defeito encontrado no produtor.

## GREEN final, evidência objetiva

[**GitHub Actions #39326874100**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39326874100): `completed/success`, HEAD `ef20571075443bf3bca3b65d3b30ca215a33beab`, jobs `118314886284` Ubuntu e `118314886940` Windows. Logs verificados:

| Suíte (por sistema) | Ubuntu | Windows |
|---|---:|---:|
| 20 cenários CAS/concorrrência/rollback dois domínios novos | 20 PASS | 20 PASS |
| 16 observação H0 SQLite sem witness | 16 PASS | 16 PASS |
| 13 restauração oficial SQLite com execução hardstop | 13 PASS | 13 PASS |
| 15 testes de mutações de gates críticos | 15 PASS | 15 PASS |
| 5 A73 witness + 4 A110 reenvio ambíguo | 9 PASS | 9 PASS |
| **Total** | **73/73 PASS** | **73/73 PASS** |

**73 casos distintos, 146 execuções PASS**; `P0_H0_CURRENT_NO_WITNESS_BARRIERS_PINNED` validado nas duas plataformas. Nenhuma suíte demonstra disponibilidade/segurança real de Cloudflare nem substitui os Quality/Security canônicos RED.

## Resultado principal: CAS funciona NO MODELO, mas confiabilidade externa falta
1. Custody seq1 e local seq0 depois de restaurar APENAS o executor -> `MODEL_LOCAL_ROLLBACK_SUSPECTED`, mas ainda `BLOCKED`.
2. Custody seq0 e local seq1 depois de restaurar APENAS o custodiante -> `MODEL_CUSTODY_STALE_OR_FORK_SUSPECTED`, ainda `BLOCKED`.
3. **Rollback coordenado de ambos** -> local seq0 e custody seq0 de novo parecem iguais; o teste 16 retorna `MODEL_HEAD_MATCH_ONLY_NO_EXTERNAL_PROOF`, `rollback_ruled_out=false`, `first_effect_allowed=false`. **Nenhum checksum local, assinatura feita pelo administrador da mesma conta ou CAS refeito pode provar que o evento apagado não ocorreu**.
4. Timeout após reserva CAS modelada -> pedido repetido encontra `MODEL_ATTEMPT_ALREADY_RESERVED_UNKNOWN_EFFECT`; NUNCA habilitar retry cego, despachos externos ou Worker.
5. Um ledger do custodiante deve estar fora do domínio de restauração e da administração do executor; Cloudflare DO em conta separada pode ser candidato operacional, mas **sem uma âncora adicional imune à restauração por admin/conta, DO sozinho não é suficiente**.

## Próximos bloqueios de execução

Antes de escolher/provisionar Cloudflare: definir administradores/identidade em contas distintas e **terceiro domínio de âncora imutável/durável** (WORM/append-only e trilha auditada), autenticar issuer/key version por enrollment real, teste de CAS remoto com rollback/PITR e perda de resposta, custo e quotas com bloqueio, auditoria LGPD, producer receipts com no-effect terminal e HUMAN_OWNER. Todos esses itens permanecem não testados/sem autorização. Cloudflare no Free é plano para análise; não habilita GLOBAL Worker do AION.

**Conclusão operacional:** contrato de arquitetura e experimento offline com 146 execuções validadas; **0/6 P0 homologados, HARD NO-GO, Worker desligado, ZERO_AUTO_RESEND.**
