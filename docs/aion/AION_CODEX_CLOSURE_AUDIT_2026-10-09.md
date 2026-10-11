# AION — Relatório de fechamento técnico independente
Data: 09/10/2026. Estado: **HARD NO-GO / INSTALLER BLOCKED**.

## Identidade, preservação e escopo
- Repositório: aparecidomikael97-ship-it/usd-macro-pro-v4.
- A pasta originalmente aberta não é Git: rev-parse/status/branch falharam.
  Nenhum arquivo preexistente dessa pasta foi sobrescrito.
- Worktree gerenciado indisponível: ferramenta retornou "Not a git repository".
  Foi criado clone novo isolado em .codex-aion1155-audit-20261009.
- Base exata: ded414b10e393f1ff7dd6cdba57fc6062c247c5e (#1155).
- Branch própria: codex/aion-1155-closure-audit. Base obrigatória:
  ded414b10e393f1ff7dd6cdba57fc6062c247c5e, com patch em 11 arquivos.
  O HUMAN_OWNER autorizou explicitamente um commit e uma única Draft sobre
  #1155. O SHA publicado e o resultado do CI serão registrados na entrega;
  os 171 testes locais correspondem à árvore preparada, não ao CI remoto.
- Sem reset/clean/force-push, merge, deploy, mudança de main ou branches alheias.
- Nenhuma alteração nos módulos Core V1, activation gate, feature flags,
  checkpoint operacional, worker, chaves, sandbox físico, firewall ou serviços.
- GETs de código/metadata e eventual publicação de código/PR são operações
  de desenvolvimento autorizadas, não chamadas da aplicação com credenciais reais.
- Nenhum provider, trading, pagamento, publicação de conteúdo ou am12 acessado.

## Evidência executada
1. Quatro suítes solicitadas: **37 testes aprovados** na base ded414b.
2. Dois testes legados de stores (24 métodos) contra módulos carregados do
   git show ded414b: **20 aprovados / 4 falhos / 0 erros**. As quatro falhas
   preexistentes esperavam retry após 409 e sucesso de 201 sem readback.
   Fixtures foram corrigidas para bytes/SHA reais sintéticos e duas leituras;
   a exigência de não repetir foi reforçada, não removida.
3. Novas regressões antes do patch: **8 métodos, 17 falhas em subcasos**;
   após patch: **8/8 aprovados**. Não são 17 testes independentes.
4. Runner ampliado: **171 métodos aprovados**, sem falhas/erros, incluindo
   guardas URL/status/redirect, auditor de egress e os 24 testes legados.
   Comando reproduzível: python -B scripts/aion1155_closure_audit.py
5. Auditores estáticos: 21/21 writes em 14 módulos; 28/28 GETs em 12 módulos;
   21 destinos válidos/no-redirect; dois POSTs pagos continuam hard-denied.
   Auditor integral inicial: 585 arquivos Python de produção, zero violações.
6. Incidentes de execução documentados: um comando inicial teve erro de quoting;
   15 fixtures tiveram PermissionError no TEMP do sandbox. Reexecutadas em pasta
   de fixtures do checkout. Uma execução ampliada incluiu fixtures transitórias
   no inventário produtivo; mover fixtures para tests/.audit-fixtures resolveu
   sem alterar o auditor. Não houve falha de rede nem relaxamento de proteção.
7. Não executado unittest discover irrestrito: a árvore inclui integração
   loopback/TLS e outros testes fora da autorização de execução física.
   Não instaladas dependências; Python local 3.12.10 e requests existentes.
8. Os nove arquivos Python alterados/novos passaram compile() sem executar
   aplicação; git diff --cached --check passou após remover duas linhas
   vazias finais. O runner foi reexecutado no patch final.

## Autorização de publicação
A revisão automática havia rejeitado github_create_tree sob as restrições
read-only anteriores. Nenhum mecanismo alternativo de push foi tentado.
O HUMAN_OWNER forneceu depois autorização explícita para publicar exatamente
os 11 arquivos na branch própria e abrir uma única Draft sobre #1155.
A publicação permanece condicionada à aprovação normal da ferramenta;
qualquer bloqueio persistente deve encerrar a tentativa, sem contorno.
Checkpoint #1117 permanece HARD NO-GO; nenhum merge/deploy está autorizado.

## Achados reproduzidos e correções mínimas

### F1 — HIGH — GET sem conteúdo pode autorizar sobrescrita
Arquivos: atlasquant_flight_recorder_store.py::_fetch_remote;
atlasquant_research_evidence_store.py::_fetch; atlasquant_shadow_store.py::_fetch.
Na base: Flight 104–105, Research 173–175, Shadow 84–86.
Um HTTP 200 com sha, sem content ou encoding=none, virava lista vazia.
O writer emitia PUT com o SHA existente e somente os novos registros.
O readback posterior não impede a perda anterior.
**Corrigido:** decode_verified_github_contents exige envelope base64, SHA
40-hex, decodificação estrita, UTF-8 e SHA Git recalculado dos bytes antes do parse.
Conteúdo indisponível bloqueia; não se busca download_url nem se acrescenta HTTP.
Regressão: test_missing_or_unavailable_get_content_cannot_overwrite_existing_blob.
Risco de compatibilidade deliberado: respostas encoding=none/grandes demais
ficam indisponíveis; nunca são interpretadas como arquivo vazio.

### F2 — HIGH — normalização JSON escondia bytes divergentes no readback
Arquivo: atlasquant_aion_v2_legacy_github_contents_readback.py::verify_legacy_jsonl_readback
mais os três leitores acima. Na base helper 47–56.
Fixture devolve SHA do texto esperado mas bytes contendo
"value":999,"value":1. json.loads elimina a primeira chave; reserialização
coincide com o esperado. Os três writers retornaram SAVED/verified=True.
**Corrigido:** o mesmo decode_verified_github_contents verifica os bytes
originais antes dessa perda de informação. Resultado agora UNKNOWN_OUTCOME,
safe_to_retry=false e um único PUT.
Regressão: test_readback_duplicate_json_key_cannot_hide_different_bytes.
Não se reivindica autenticidade independente: respostas inteiramente forjadas
e mutuamente consistentes continuam fora da prova.

### F3 — HIGH — replay indireto sobrevivente no orçamento
Arquivo: twelve_budget_v1108.py::GitHubStore.save / Budget._change.
Na base save 74–83 e _change 113–124.
409/422 retornavam False; _change repetia até quatro GET/PUT.
Reprodução com ambos os status: **4 PUTs**, mesmo depois de #1154.
**Corrigido:** o store GitHub levanta BudgetUnavailable com motivo de
reconciliação/no-retry; _change interrompe. Nenhuma mudança no cálculo de créditos,
limites, provider ou CAS de stores puramente locais.
Regressão: test_budget_reported_conflict_never_replays_at_higher_layer;
timeout também mantém um PUT.
Limite: chamadas futuras separadas ainda não têm journal durável global.

## Lacunas remanescentes — NÃO fechadas por este patch

### R1 — HIGH — 12 writers Contents continuam com confirmação apenas HTTP
São 17 sites Contents: 3 JSONL com readback; 2 checkpoints com readback/digest;
**12 restantes sem readback do conteúdo**:
- autopilot_v107.py::gh_put_bytes (221–222).
- currency_news_v1061.py e currency_news_v1062.py::_gh_write_csv_v1061 (997–998).
- currency_news_v107.py::_gh_write_csv_v1061 (1005–1006).
- market_map_v10.py::_save_snapshot (134–135).
- master_panel_v102.py::_save_state (145–146).
- twelve_budget_v1108.py::GitHubStore.save (base 81–83).
- usd_macro_pro_v4_cloud.py::_github_salvar_csv_v84 (3623–3624),
  _github_put_bytes_v104 (4459–4460), _salvar_feedback_v104 (4506–4507),
  _autopilot_save_inputs_v107 (4624–4625), _config_salvar_v937 (8327–8328).
Evidência runtime sintética: GitHubStore.save recebe 201 com {} e retorna True.
Teste existente de gh_put_bytes aceita 200 sem content receipt.
Guardas de status são reais, mas não provam conteúdo persistido.
Proposta: migrar por família para receipt+readback e UNKNOWN_OUTCOME, com
revisão de consumidores antes de alterar interfaces legadas; não merge bruto.

### R2 — HIGH — UNKNOWN_OUTCOME apagado em camada de sessão
atlasquant_shadow_capture.py::capture_shadow_batch (95–109):
ensure_shadow_hydrated fornece o status anterior, descartado por rows,_.
Se nada novo for acrescentado, grava ok=True/ALREADY_PRESENT.
Reprodução AST da função real com fixture de sessão já preenchida após
UNKNOWN_OUTCOME retornou sucesso e removeu reconciliation_required.
atlasquant_research_evidence_capture.py::capture_research_evidence (103–126)
tem caminho análogo. persist_session_research_evidence (150–168) não aplica
quarentena anterior antes de uma nova chamada ao writer.
Proposta: preservar pendência e distinguir presença local de persistência;
journal por operação/scope para bloquear replay entre sessões/processos.
Não houve prova de repetição AUTOMÁTICA nessa UI; o replay automático
efetivamente reproduzido nesta auditoria foi F3.

### R3 — MEDIUM — 409/422 tratados como conflito reconciliado nos checkpoints
atlasquant_aion_memory.py::save_runtime_checkpoint (2334–2348) e
atlasquant_aion_global_worker.py::_persist_runtime_checkpoint_cas (1223–1237):
ambos agrupam 409/422 como CONFLICT, reconciliation_required=false.
É um fato estático, não prova de gravação real nem de worker ativo.
Contrasta com os três stores que declaram REPORTED_* e pedem reconciliação.
Proposta: unificar semântica reportada/UNKNOWN e revisar consumidores do
receipt sem alterar a cadeia congelada nesta correção.

### R4 — MEDIUM — ALREADY_PRESENT não compara todo o conteúdo
merge_unique_records / merge_evidence_records / merge_unique_samples deduplicam
pela identidade declarada. Mesmo id com conteúdo diferente pode ser ignorado
e terminar ALREADY_PRESENT. Isso é presença de chave, não confirmação do pedido.
Proposta: definir explicitamente imutabilidade por identidade e bloquear
colisões de conteúdo; não mudar a política histórica silenciosamente.

### Limites adicionais de evidência
- Os quatro sites Actions variables têm guardas; WRITE_ACCEPTED é intermediário.
  O orquestrador em atlasquant_aion_global_worker_activation.py faz releitura.
  force_disable_repository_feature_flag isolado retorna DISABLED só pelo HTTP;
  erro retorna modified=false mesmo quando o envio pode ter ocorrido.
  Não se certifica o estado real da flag por esses resultados isolados.
- URL guard fixa origem e gramática, NÃO o repo autorizado ou escopo do token.
- HTTP 404 pode ocultar ausência de permissão; não prova ausência do arquivo.
- Same-origin SHA/readback não é witness independente, autenticidade TLS,
  durabilidade, proteção contra proxy que repete PUT, nem exactly-once.
- Limitação por invocação não impede outro processo, nova sessão ou retry externo.
- Nenhuma concorrência real entre dois processos nem falha física de energia
  foi exercitada aqui. CAS/proxies/restart continuam dependências de integração.
- Serialização/parse malformados e SHA obsoleto são cobertos em mocks; bytes
  coerentes com origem falsa, credenciais reais e proveniência faltante não
  podem ser certificados com mocks.

## PRs e CI observados
Todas #1149–#1155 estavam **OPEN/DRAFT, não merged** na consulta:
| PR | HEAD | Entrega |
|---|---|---|
|1149|8d1d0895332d439090d9a6e4c32215cd814646ce|21 URL guards/no redirects|
|1150|63237be98208810fdd9dc56b26ae8377fe6ff01c|28 token GET guards|
|1151|2c6aecc3672173f81e04ff211b7457fbd9bbbe07|status GET|
|1152|5f0c285ac9faef7aff3ce88f3402dc6166b09ffd|status write|
|1153|340d825ea02d90783c291c07f55b158a942e61c1|UNKNOWN nos três JSONL|
|1154|0e91e4dc19af9529c4b29a8370f485e55daa2b6b|no replay em quatro funções|
|1155|ded414b10e393f1ff7dd6cdba57fc6062c247c5e|SHA PUT + readback JSONL|

#1155: 8 jobs SUCCESS no SHA exato, quatro workflows:
[write status](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/37999904412),
[GET status](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/37999904422),
[GET URL](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/37999904452),
[write URL](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/37999904483).
O último comentário lido de #1117 ainda dizia CI em andamento para #1155;
a consulta direta aos checks confirma conclusão. A issue não foi alterada.
CI da correção é independente e deve ser consultado no HEAD da nova Draft;
não herda aprovação automática da base.

## Matriz de fechamento versus #1117
| Grupo | Evidência | Pendência / responsável |
|---|---|---|
|Núcleo implementado|URL/status/redirect nos 49 sites; hard-deny text/TTS; receipts locais|não significa instalação segura|
|Aprovado em CI|quatro workflows #1155, Ubuntu+Windows|rodar nova Draft no HEAD exato|
|Lacunas de código|F1–F3 corrigidos; R1–R4 abertos|revisão por família e consumidor|
|Integração|#1116 e #1114 são linhas separadas|adapter de evidência, trusted roots e recovery|
|Prova física|nenhuma nova neste trabalho|12 categorias/16 superfícies; coletor independente|
|HUMAN_OWNER|nenhuma aprovação de instalação inferida|D1 witness, D2 Ed25519, D3 P256, D4 recuperação, D5 ensaios, D6 pacote|
|Produção/primeira instalação|HARD NO-GO|identidade, custódia, antirollback, tempo confiável, supply chain e autorização separada|

## Plano de integração #1116 + #1114 — não executado
- #1116 HEAD e333fd7b2f44c256f9fcf629b8bcc8aae46bcfe7: ler/reutilizar
  LifecycleAdapter.prepare/run/recover, verify_request, verify_checkpoint e
  LifecycleWitnessState. run altera ledger de referência; recover reconcilia
  a mesma reserva e não reexecuta a ação.
- #1114 HEAD 2a4c79480e1171dfa99d96dbacfdf49db8a21500: reutilizar
  review_untrusted_appcontainer_localhost_observation. A saída máxima é
  LOCAL_LOOPBACK_DENIAL_CANDIDATE_UNTRUSTED, não atestação física.
- Esses dois módulos não estão presentes na árvore base #1155 inspecionada.
  Não basta transportar uma função: incluir dependências transitivas das
  bases #1115/#1113 e #1091/#1089, com SHA/versionamento explícitos.
- Primeiro: inventário de contratos/schemas e hashes das árvores a integrar.
- Segundo: adapter data-only que vincule observação original, nonce, instalação,
  trust chain, processo/imagem, escopo/limites e policy generation à proposta
  assinada existente. Assinar um candidato não o transforma em prova física.
- Terceiro: testes sintéticos de replay, troca de owner/collector/scope,
  relógio desconhecido, lost ACK, PREPARED órfão, mismatch before/after,
  dois processos e recuperação sem novo write. Separar testes físicos.
- Não duplicar CAS/nonce ledger; não aceitar pin/chave do próprio pedido como
  enrollment; não conectar testemunha RAM como autoridade de produção.
- Witness persistente independente, custódia e recovery continuam design
  aprovado pelo HUMAN_OWNER, sem serviços pagos ou provisioning nesta missão.
- Testar combinação em branch futura antes de qualquer pedido de integração.
  Nenhum merge das frentes foi feito ou recomendado sem revisão do diff.

## Inventário Windows futuro — PROPOSTA, NÃO EXECUTADO
Somente após autorização específica, em host explicitamente autorizado que
NÃO seja am12. Usar sessão PowerShell já aprovada. Não criar serviço/processo
de ensaio, conectar rede, consultar TPM/Hello/FIDO2 ou gerar chave.

| Comando proposto | Resultado esperado / risco / rollback |
|---|---|
|Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' \| Select-Object ProductName,DisplayVersion,CurrentBuild,UBR|versão local; não prova segurança; somente leitura, rollback N/A|
|Get-Service -Name MpsSvc,BFE \| Select-Object Name,Status,StartType|estado dos serviços; não prova negação de rede; sem Start/Stop/Set; rollback N/A|
|Get-NetFirewallProfile \| Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction|configuração dos perfis, sem testar tráfego; acesso negado vira UNKNOWN, sem elevação automática; rollback N/A|
|[Security.Principal.WindowsIdentity]::GetCurrent().Groups \| Select-Object Value|SIDs de grupos do contexto; informação identificadora a redigir antes de compartilhar; não equivale a token do child; rollback N/A|

Hash do coletor somente depois de existir caminho aprovado: Get-FileHash
-LiteralPath '<CAMINHO_EXATO_APROVADO_DO_COLETOR>' -Algorithm SHA256.
O placeholder impede execução automática; hash comprova identidade de bytes,
não origem confiável nem autorização. Sem instalação/download/execução.
TPM/provedores/attestation, perfis AppContainer, handles e controles positivos
ficam para plano próprio, aprovado por ação; qualquer bloqueio encerra o ensaio,
sem workaround. Nenhum desses comandos foi executado nesta auditoria.

## Prioridades
1. Revisar o pequeno patch F1–F3 e CI da Draft no HEAD exato; não integrar sozinho.
2. Fechar R2 (incerteza persistente nos consumidores) e R1 (12 confirmations HTTP),
   preservando contratos e bloqueando repetição entre invocações.
3. Reconciliar R3/R4 e completar integração data-only das duas frentes.
4. Design de witness/custódia/recovery com HUMAN_OWNER; só depois propor ensaios
   físicos separadamente e fora de am12.
5. Instalação/build/deploy continuam sem autorização.

**Resultado: HARD NO-GO. Não autoriza instalação, worker, produção ou gasto.**
