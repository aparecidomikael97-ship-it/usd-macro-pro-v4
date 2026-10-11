# AION — preparação mestre offline P0

11/10/2026. Estado: **HARD NO-GO**. Não constitui autorização de instalação.

## Base e reconciliação

Base obrigatória #1216: `895f3abcd533684ee1eab9b92b6ce9eebf3b74be`, branch `audit/aion-first-install-readonly-plan-v1-20261011`. Main observada: `5744b2b7b17c84331e6f27c569064993ff587782`. A árvore do arquivo baixado foi reconstruída localmente com hashes Git e coincidiu com `8b27b160fd3fe1bc20b8c7268fdb12fafbd7f367`. A preparação é uma pasta isolada, sem modificar os worktrees anteriores; a branch de publicação será filha direta da HEAD obrigatória.

Os treze compares #1204–#1216 estão `ahead` das respectivas bases, com zero commits atrás. #1191 (`7d4af5e45b8e80ca43e65171d28255510b76b3b1`) também é ancestral da árvore #1216. Isso foi verificado, não presumido a partir dos títulos. SHA, base, checks inspecionados e URLs estão em `evidence/AION_FIRST_INSTALL_PREPARATION_BASELINE_20261011.json`. O compare main→#1216 excede a página de 300 arquivos; o arquivo integral e a reconstrução da árvore evitam auditar uma lista truncada como se fosse completa.

Provas de testes da base:

- #1214 / `103148a2212e6206106a57edb827006582aaab66`: [Quality real](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38108677611/job/114379487703), 569 módulos descobertos/listados, zero ausentes; **6.348 testes, OK**, 44,962 s, Linux.
- #1216 / HEAD obrigatória: [Linux](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38111801872/job/114388732922) e [Windows](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38111801872/job/114388732833): 10 + 6 + 22 = **38 testes em cada sistema**. Não são provas físicas.
- Resultado negativo preservado: #1213 / `0dffba20c09f196b80e371439d8ca7d8a65de181` executou 6.345 testes e falhou na comparação que exigia `main` mesmo em PR empilhada. [Log](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38108101855/job/114377790160). A correção de comparação pertence à #1214, não a esta missão.
- #1207 tem checks Shadow verdes e um workflow de 336 testes vermelho (9 falhas) com expectativas incompatíveis de status `HARD_DENIED`/`CORRUPT_REMOTE`/`UNSAFE_BRANCH`. [Log negativo](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/38101597085/job/114358462610). Não se declarou a cadeia inteira verde só por selecionar checks positivos; os contratos foram reconciliados em SHAs posteriores.

## Lacuna reproduzida e correção mínima

**MEDIUM / veracidade de resultado em referência offline:** `atlasquant_aion_v2_isolated_sqlite_witness_cas_reference.py`, `ReferenceIsolatedSqliteWitnessCAS.cas_reference_only`. Um wrapper descartável chama o commit SQLite real e depois lança `OperationalError`. Na base, o chamador recebe `BLOCKED`, `REFERENCE_SQLITE_CAS_ROLLED_BACK`, contagem 0, embora um snapshot leia **1 append**. A reprodução falhou como esperado antes da correção; log local preservado em `.offline-tmp/baseline-postcommit-reproduction.log`.

Correção: marcar a tentativa de commit e retornar `UNKNOWN_OUTCOME`, contagem desconhecida (`None`), quando a confirmação é incerta ou o rollback falha. Não declarar ausência nem repetir. O teste abre outro processo e confirma somente a presença local causal/idempotente; não concede autoridade externa. O trigger que falha antes do commit continua demonstrando rollback real, com seus testes originais intactos. Nenhum teste antigo foi removido ou enfraquecido.

**MEDIUM / fronteira de entrada:** o planejador V1 não limita a coleção de gates nem rejeita campos extras. Como sempre retorna NO-GO, não foi comprovado bypass de instalação. O novo `plan.review_evidence_plan` exige exatamente 20 registros, schemas fechados e strings limitadas antes de delegar ao V1. V1 e manifesto original permanecem intactos.

**HIGH / bloqueio operacional existente, não resolvido por código:** não há identidade física HUMAN_OWNER, matrícula independente de dispositivo/chaves, testemunha externa protegida ou prova de recuperação em dois domínios. Nenhuma assinatura de fixture, configuração, token ou SHA soluciona essa ausência. Todas as 20 gates continuam pendentes.

## Código entregue e compatibilidade

Pacote `atlasquant_aion_first_install_preparation`: `contracts`, `ceremony`, `windows`, `recovery`, `governance`, `plan`. Funções de revisão puras, entradas limitadas, decisões de simulação explicitamente rotuladas. `production_authority` tem apenas recusa; não invoca callbacks nem lê ambiente. Não há função de execução, probe, coleta de hardware, matrícula, criação de chave, rede ou escrita de checkpoint.

Arquivos reais examinados: `atlasquant_aion_first_install_plan_v1.py`, manifesto original, `atlasquant_aion_global_worker_source_gate_v1.py` (`independent_worker_source_preflight`), `atlasquant_aion_global_worker.py` (`global_worker_feature_enabled`, `run_global_worker_once`), `atlasquant_aion_global_worker_activation.py`, `atlasquant_aion_memory.py`, `atlasquant_runtime_store.py`, `atlasquant_aion_trust_root.py`, `atlasquant_aion_nonce_registry.py`, `atlasquant_aion_owner_signature_ceremony.py`, `atlasquant_aion_owner_experience_v1.py` (`owner_binding`), `atlasquant_aion_checkpoint_dual_challenge_reference_v1.py`, referências SQLite/CAS, journal e reconciliação UNKNOWN, `atlasquant_aion_execution_outbox.py`, contratos/testes históricos e políticas de convergência.

Core V1, gates reais, autenticação, Worker, memória, outbox, registry e configurações produtivas não são modificados. A única alteração em código existente é na referência SQLite sem autoridade. A cerimônia antiga verifica posse da chave cadastrada e estado; não prova por si só identidade civil, dispositivo Windows ou custódia externa. `owner_binding` depende de uma assertion já verificada pelo host e retorna `grants_authority=false`; não se conecta a ela uma fixture nova.

O Worker é desligado por padrão no código e seu source preflight sempre bloqueia antes de GET/CAS/execução. Não foi consultada nem alterada a flag em produção. Core freeze/preflight e gateway de ferramentas permanecem intactos. A proteção de caminho Windows desta preparação é lexical para um recurso lógico: não prova File ID, reparse points, ACL, volume ou ausência de TOCTOU físico.

## Testes e limites de cobertura

Dois novos módulos de teste cobrem 68 testes de contratos e 8 de processos/referência; o runner também reutiliza testes originais de witness, journal, assinatura/challenge, memória, autenticação e browser reconciliation. Execução local antes da publicação: **243 testes + 375 subtestes, zero falhas/erros/skips/expectedFailure**, 33,558 s. O resultado definitivo por HEAD estará na PR/CI. Um ajuste posterior na ordem da coleta coloca aprovação financeira antes da preparação de provas que podem exigir providers pagos; o DAG permanece sem ciclos e não autoriza a provisão.

`tools/aion_first_install_preparation_ci.py` bloqueia conexões de rede e mede linhas executadas e corpos de funções com `trace` da biblioteca padrão. O JSON em `artifacts/` é produzido pela execução. Não alegamos percentual de branch coverage, cobertura de código nativo Windows ou testes em máquinas independentes fisicamente confiáveis. CI Windows/Linux e o Quality Linux exato serão executados no HEAD publicado; resultados anteriores não serão usados como aprovação desse HEAD.

Não houve instalação de dependências no computador do proprietário. As dependências já fixadas são instaladas somente nos runners descartáveis de CI. Não houve deploy, publicação de produto, Worker, provider pago, matrícula externa ou acesso a dados privados. PR Draft e código de preparação não constituem GO.

Compilação local: o comando comum `compileall` encontrou `FileNotFoundError` ao criar nomes de bytecode temporários sob o caminho longo desta cópia Windows. Não foi alterada a configuração de segurança/long paths. A compilação de **1.253 arquivos Python** com `py_compile`, escrevendo somente bytecode em um diretório temporário curto descartável, passou integralmente. Os 92 testes por `unittest discover -s tests -p test_aion_first_install*.py` também passaram. O CI executa `compileall` normal em seu workspace curto; não se declarou o comando local original aprovado.

## Próximo trabalho sem acesso físico

Finalizar o contrato do verificador WebAuthn/RP com vetores oficiais e fixtures, o protocolo de high-watermark/fork em providers falsos e o formato privado de evidências. Preparar ensaios de storage/ACL/recovery em VM descartável, somente com autorização específica para esse ambiente. Cotação real, matrícula, captura física, biometria/chaves, instalação e execução dependem de etapas separadas; nada disso é autorizado pelo resultado deste pacote.
