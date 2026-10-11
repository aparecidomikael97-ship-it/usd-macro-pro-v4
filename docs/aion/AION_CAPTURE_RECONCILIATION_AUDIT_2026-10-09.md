# Shadow / Research — UNKNOWN_OUTCOME consumer audit

Base: PR #1156, `5a064ca4b0a6cdc28d62d5e1ccf9a1383a5a4473`.
Branch local: `codex/aion-unknown-outcome-consumers`.
HEAD permanece na base; patch local preparado, sem commit/push/PR.
O clone anterior e seus 11 arquivos staged foram preservados. Esta auditoria
usa um worktree separado, criado no commit exato obtido por GET/fetch de código.

## Diagnóstico comprovado na base

| Severidade | Arquivo / função / linhas na base | Reprodução e impacto |
|---|---|---|
| HIGH | atlasquant_shadow_capture.py / capture_shadow_batch / 96–118 | Após timeout de PUT, repetir a mesma captura descarta o status anterior e produz ok=True/ALREADY_PRESENT. Uma captura distinta chama novamente o store e pode substituir a pendência por SAVED. Presença na lista local não reconcilia o primeiro PUT. |
| HIGH | atlasquant_research_evidence_capture.py / capture_research_evidence / 102–147 | Duplicação local vira ALREADY_PRESENT; persist=False também substitui UNKNOWN_OUTCOME por estado local bem-sucedido. Nova captura com persistência chama novamente o writer. |
| HIGH | atlasquant_research_evidence_capture.py / persist_session_research_evidence / 151–168 | Desconsidera o status retornado pela hidratação e pode chamar novamente o store. GET com os mesmos IDs produz ALREADY_PRESENT sem reconciliação do write anterior. Cache local vazio pode produzir NO_RECORDS e apagar a pendência. |

Limite existente: os stores já retornam UNKNOWN_OUTCOME,
reconciliation_required=True e safe_to_retry=False após tentativa incerta,
com apenas um PUT por chamada. Essa proteção não sobrevivia à próxima chamada
dos consumidores. Reidratar com HYDRATED_KEY=False podia também trocar a
pendência por LOADED. Não foi necessário provider ou rede real para reproduzir.

## Correção mínima proposta no diff

- Um PENDING_KEY separado por consumidor mantém a quarentena de sessão.
  UNKNOWN_OUTCOME, CONFLICT, VALIDATION_REJECTED ou reconciliação exigida
  prevalecem sobre status aparente de sucesso. Status legado é adotado.
- Hidratação, captura e persistência em lote consultam a pendência. Enquanto
  ela existe, nenhum GET/PUT é iniciado por esses caminhos; novos dados ainda
  podem ser registrados localmente. local_added e session_* são contagens locais.
- Duplicação local usa LOCAL_ALREADY_PRESENT/source=session,
  persistence_confirmed=False. Não usa ALREADY_PRESENT do store remoto.
- SAVED só recebe persistence_confirmed=True com verified=True e
  readback_matching_content=True do store. confirmation_scope=CURRENT_WRITE_BATCH
  limita a confirmação ao lote enviado; não confirma toda a sessão ou durabilidade.
- Cópias dos dicionários impedem que mutar o resultado retornado ou o status de
  exibição apague a pendência separada. Não há clear/reset/reconcile permissivo.
- Admin Research informa a pendência, desabilita o botão e continua protegido
  no serviço caso o handler seja invocado. ALREADY_PRESENT remoto significa
  presença por ID; a tela não o apresenta como confirmação integral.
- O runner offline e o filtro de paths do workflow incluem as novas regressões.
  Nenhum check anterior foi removido. Não houve execução de CI remoto do patch.

Não existe atualmente nestes consumidores um contrato suficiente para liberar
a quarentena por reconciliação. Por isso o patch bloqueia e não inventa prova.
Não limpar session_state manualmente para retomar uma operação incerta.

## Revisão dos consumidores reais

| Consumidor | Resultado da revisão |
|---|---|
| atlasquant_admin_research_panel.py / render_admin_research_panel | Serviço de persistência em lote bloqueado; aviso/botão e mensagem de confirmação corrigidos. Testes executam o bloco AST real do botão com serviço real e estado sintético. |
| atlasquant_backtest_panel.py / chamadas capture_research_evidence | Ambos os caminhos usam persist=False; podem continuar lembrando evidência local sem substituir a pendência. Nenhum write adicionado. |
| pair_intelligence_v110.py / chamada capture_shadow_batch | Usa o consumidor corrigido; resultado de captura não concede execução. |
| usd_macro_pro_v4_cloud.py / ensure_shadow_hydrated | Hidratação corrigida preserva a pendência; resumo/validation recebem amostras locais e não são prova de persistência remota. A UI completa não foi executada. |
| atlasquant_research_evidence_capture.py / latest_research_evidence | Continua oferecendo leitura local; não limpa o status pendente nem consulta rede. Não certifica origem remota de cada registro. |
| autopilot_v107.py / persist_decision_evidence / 1297–1320 | HIGH residual: chama persist_shadow_samples diretamente e não usa a quarentena de sessão. Duas execuções da função real, extraída por AST, deram UNKNOWN_OUTCOME → ALREADY_PRESENT, 2 GET e 1 PUT simulados. Não executamos o Autopilot/Worker. |

## Testes e resultados reais

- `python -B -m unittest discover -s tests -p test_atlasquant_capture_reconciliation.py`:
  regressões offline descobertas pelo unittest; o arquivo final possui 19 métodos.
- `python -B scripts/aion1155_closure_audit.py`: **190 testes PASS**, incluindo
  os 19 novos e os 171 herdados; execução final em 25,691 segundos.
- Avaliação anterior dos primeiros 17 métodos sobre fontes da base carregadas
  em memória: **30 subcasos falharam e 4 erros de campo ausente**. Os quatro
  KeyError correspondem ao novo campo persistence_confirmed, não a quatro
  vulnerabilidades adicionais. Foram observadas transições reais para
  ALREADY_PRESENT/SAVED e novos PUT após timeout. Testes não foram afrouxados.
- Cobertura: timeout de PUT; 201 válido seguido por timeout de readback;
  duplicata/nova captura/lote; persist=False; cache vazio; reidratação;
  sobrescrita do status; mutação do retorno; flag de reconciliação com receipt
  aparente; troca de configuração; conflict/422; presença por ID; captura local;
  SAVED legítimo com SHA/readback; leitura local; handler e disabled do Admin.
- Todos os testes usam token sintético, estado sintético e bloqueio de socket
  connect/connect_ex/create_connection e HTTP não mockado. Imports opcionais de
  Streamlit são substituídos por módulo de teste; nenhuma leitura de secrets/UI.
- Suíte antiga `test_atlasquant_shadow_persistence.py`: **9 PASS / 1 FAIL**.
  `test_create_remote_file` ainda espera sucesso com bare 201 sem SHA/readback;
  a mesma falha foi reproduzida no store da base #1156. Arquivo preservado.
  Deve receber fixture válida em revisão própria; não remover a verificação.
- Cinco arquivos Python alterados/adicionados compilados em memória: PASS.
  `git diff --cached --check`: PASS.
- Sem instalação de dependências. Streamlit/pandas não estão disponíveis neste
  Python; a UI completa e a suíte ampla Research com pandas não foram executadas.
  Não foi executado discover irrestrito que inclui testes físicos/loopback/TLS.

## Riscos residuais e conclusão

- **HIGH / comprovado:** chamada direta do Autopilot ao store contorna o gate
  de sessão. Outros callers futuros do store terão a mesma obrigação de não
  tratar presença por ID como reconciliação. Esse caminho não foi alterado.
- **HIGH / limite estrutural:** session_state não é journal durável. Reinício,
  nova sessão ou outro processo perdem o marcador e podem repetir o write.
  O patch não é exactly-once global nem proteção contra rollback.
- **HIGH / concorrência não fechada:** leitura do gate e início do writer não
  são claim atômico/CAS. Não foi comprovada por ensaio multithread nesta auditoria;
  não afirmar proteção de operações simultâneas ou de write ainda em andamento.
- **MEDIUM:** IDs iguais não comparam o conteúdo integral nos stores; o patch
  mantém esse fato explícito e não usa esse resultado para liberar uma pendência.
- **MEDIUM / disponibilidade:** a quarentena bloqueia a persistência da sessão
  inteira, inclusive nova configuração, até existir reconciliação legítima.
  Leitura/hidratação remota não é usada como liberação automática.
- Hash e readback continuam comprovando consistência da resposta recebida;
  não comprovam origem independente, durabilidade remota ou autoridade física.

Conclusão: **PARTIALLY_CLOSED**. A perda sequencial de estado nos consumidores
Shadow/Research é mitigada no patch local; reconciliação durável entre processos
e callers diretos continua pendente. Próximo bloco: revisar um contrato de
reconciliação vinculado à operação, conteúdo e escopo, com recuperação da
quarentena e revisão do caller direto; reutilizar a cadeia existente, sem novo
sistema de autoridade e sem habilitar writes físicos ou provider.

**Checkpoint #1117 permanece HARD NO-GO.** Nenhum commit/push/PR, merge,
deploy, instalação, Worker, acesso a am12/TPM/Windows físico, matrícula de chave,
credencial real de aplicação, trading, pagamento ou serviço pago foi executado.
