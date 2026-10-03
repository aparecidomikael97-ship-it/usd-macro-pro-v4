# AION Chat Foundation V1 — issue #537

## Escopo e estado verificável

Fundação local isolada, sem integração na Central geral. Não importa nem modifica
shell premium, Central, startup, login, RBAC, providers, Engine, Safety Core,
score, trading, Render ou workflows existentes. Nenhuma ação física é executada.

| Capacidade | Estado |
| --- | --- |
| Modelos, SQLite, histórico, paginação e busca | IMPLEMENTED / TESTED |
| Checkpoint estruturado, resumo extrativo e retrieval literal | IMPLEMENTED / TESTED |
| Ingestão de anexos em quarentena | IMPLEMENTED / TESTED |
| UI local, envio, reabertura, feedback e mobile 390px | IMPLEMENTED / TESTED |
| Classificação e contratos de tarefa, cancelamento local | IMPLEMENTED / TESTED |
| Respostas de modelo, raciocínio, análise de documentos | NOT_CONNECTED / REQUIRES_PROVIDER |
| Execução de tarefas, aprovação efetiva e integrações AION | SHELL_ONLY / NOT_CONNECTED |
| Voz, troca de provedor e recuperação de quota externa | SHELL_ONLY / REQUIRES_PROVIDER |
| Publicação, email, merge, deploy, gastos e credenciais | REQUIRES_APPROVAL; sem executor |
| Trading real e ação desconhecida | BLOCKED |

A fundação não declara atendido o requisito de receber uma resposta real de modelo
da issue #537: isso depende de integração posterior. Mensagens de indisponibilidade
são do papel system; nunca são respostas simuladas do papel assistant.

## Arquitetura

- aion_chat/models.py: Conversation, Message, Attachment, ConversationCheckpoint,
  ContextSummary, TaskRequest, TaskResult, Scope e Page.
- aion_chat/store.py: protocolo AionChatStore e SQLiteChatStore.
- aion_chat/context.py: compact_conversation e build_conversation_context.
- aion_chat/attachments.py: política, assinaturas, sanitização e quarentena.
- aion_chat/authorization.py: classificação fail closed; não concede autoridade.
- aion_chat/privacy.py: redação de credenciais conhecidas.
- aion_chat/service.py: comandos locais e eventos de tarefa/feedback.
- aion_chat/contracts.py: adaptadores futuros sem implementações externas.
- atlasquant_aion_chat_ui.py: servidor de preview exclusivamente em 127.0.0.1.
- aion_chat/web/: HTML, CSS e JavaScript independentes do shell de produção.

O servidor possui Scope fixo definido pelo host (local-preview/local-preview/default).
Identidade enviada pelo browser nunca determina o escopo. Trata-se de um preview
de um usuário, não de um servidor multiusuário com autenticação própria.

## Persistência e compatibilidade com o projeto

Antes da escolha foram inspecionados atlasquant_aion_memory.py,
atlasquant_aion_session_memory.py, atlasquant_aion_tenant_durable_store.py,
atlasquant_runtime_store.py e ADR-0007-checkpoint-mestre-persistencia-oficial.md.

O Checkpoint Mestre continua sendo a persistência oficial do AION. Este banco é
histórico **local de staging/preview autorizado para a fundação**; não substitui,
não salva automaticamente e não verifica o Checkpoint Mestre remoto. A identidade
é scoped como no storage durable existente; timestamps UTC, JSON explícito e
digest SHA-256 reaproveitam seus padrões. SQLite foi escolhido para evitar
reescrever um arquivo de histórico completo a cada mensagem, permitir transações,
sequências por conversa, índices de escopo/recência e paginação sem materializar
todo o histórico. Usa apenas a biblioteca padrão do Python, sem serviço pago.

Tabelas:
- conversations: identidade, título, recência, archived, modelos JSON completos.
- messages: sequência monotônica por conversa, conteúdo pesquisável e modelo JSON.
- records: anexos, checkpoints e resumos com cobertura de sequência.

BEGIN IMMEDIATE aloca sequências sem corrida entre conexões. Falha em append
reverte mensagem e contador. WAL e foreign_keys são habilitados. O histórico é
append-only pela API: não existe operação de apagar mensagens/conversas. Arquivar
altera visibilidade na lista, preservando a possibilidade de reabrir.

Checkpoint e resumo são registros locais distintos; a última cobertura nunca pode
regredir. As gravações individuais são transacionais, mas o par checkpoint/resumo
não tem uma transação conjunta; em falha entre ambos o checkpoint continua
recuperável e o resumo deve ser reconstruído. O consumidor pode comparar
through_sequence e checkpoint_id antes de usar um resumo.

## Continuidade sem limite artificial

Não há contador que encerre conversa, limite de sessões, expiração ou purga.
O teste cria 1.000 mensagens, percorre todas via cursor, compacta, recupera
mensagem antiga e a última, e então salva a mensagem 1.001. Outro teste cria
65 conversas, acima do exemplo de limite artificial proibido de 50.

page_size (1..200) limita somente uma resposta de leitura. Cursor keyset:
(updated_at,id) para conversas e sequence para mensagens, em ambas as direções.
Cursores são vinculados ao Scope, tipo de leitura e filtros; não são credenciais.
Recência pode mudar durante paginação de conversas; para uma lista ao vivo o
cliente deve atualizar a primeira página. A UI carrega páginas de 30 conversas e
50 mensagens recentes, oferecendo páginas anteriores.

A busca literal pesquisa título, conteúdo e tags. API suporta tag exata, período
de updated_at em ISO UTC e archived. Não carrega milhares de conversas no processo;
o SQL pode percorrer conteúdo dentro do escopo. Busca semântica/FTS escalável e
normalização Unicode avançada são futuras extensões do storage, não declaradas
implementadas. O limite físico é espaço/saúde do dispositivo; uma falha de storage
é indisponibilidade explícita, nunca exclusão silenciosa.

## Compactação, fatos e correções

compact_conversation percorre páginas e consolida um checkpoint até uma sequência
explicitamente escolhida. Reutiliza o checkpoint anterior. Não extrai fatos
confirmados por heurística de texto ou por modelo nesta fase.

O host pode fornecer Message.metadata.memory_events com:
kind, key estável, value, confirmed opcional e resolves opcional.

Kinds: decisions, open_tasks, completed_tasks, preferences, entities, files,
pending, confirmed_facts, assumptions e execution_state. Cada valor preserva
source_message_id, truth_state e provenance. Correções usam a mesma chave e
substituem o valor consolidado, mantendo a mensagem original e sua proveniência
no histórico. completed_tasks resolve open_tasks da mesma chave. Uma pendência
só desaparece com resolves explícito ou término do contrato de tarefa correspondente.
confirmed_facts exige confirmed=true e truth_state=CONFIRMED; caso contrário o
evento permanece assumptions. Um host futuro deve validar a evidência antes de
emitir esses campos: a estrutura não é uma verificação independente de fatos.

Anexos entram como referências de arquivo; TaskRequest/estados persistidos entram
automaticamente como tarefas abertas, pendências de aprovação e estado de execução.
Cancelamento/erro são terminais locais, sem alegar que um executor concluiu trabalho.
A TaskResult futura deve conservar proveniência de execução real.

ContextSummary contém uma cauda extrativa de até 12 trechos de 240 caracteres,
com ids, papéis e verdade não verificada por padrão, mais referência ao checkpoint.
Esse resumo é um mecanismo determinístico inicial; **não é resumo semântico
completo de todo o texto livre**. Decisões/pendências em prosa que não receberam
eventos estruturados permanecem pesquisáveis no original, mas não são
automaticamente reconhecidas como decisões. Um adaptador de extração validada
deve tratar esse requisito antes de integração em produção.

Nenhuma mensagem original é editada ou apagada ao compactar.

## Contexto técnico e recuperação

build_conversation_context monta:
1. Referência ao checkpoint e resumo mais recentes.
2. Mensagens recentes paginadas, priorizando a última.
3. Campos do checkpoint, priorizando pending/open_tasks/decisions.
4. Resumo consolidado quando couber.
5. Mensagens antigas selecionadas por consulta literal e sequência.

budget_bytes limita o JSON serializado em UTF-8, não o histórico armazenado.
O adaptador de modelo deve adicionalmente contar tokens com o tokenizer do
provedor e reservar espaço para instruções, ferramentas e resposta.

Mensagens enormes entram como trechos marcados truncated com id original.
Memória que não couber marca requires_rehydration=true e mantém checkpoint_id/
summary_id. O host deve reabrir os registros ou get_message com o mesmo Scope e
planejar contexto adicional; **não deve tomar decisões consequenciais com uma
memória parcial**. Pendências grandes continuam intactas no checkpoint, mesmo que
não caibam em um contexto. Isso é engenharia de contexto finito, não contexto infinito.

Retrieval literal e ModelAdapter são separados. Rotação de modelos, quotas e
continuação de voz são contratos futuros e ainda não têm implementação.

## Anexos e privacidade

Suporte inicial: PNG/JPEG/GIF/WebP, PDF, TXT, CSV, DOCX e XLSX.
Nome Unicode normalizado, sem separadores, '..', drive ou nomes reservados Windows.
Extensão deve estar na allowlist; MIME declarado é só metadata. Assinaturas são
validadas contra a extensão. TXT/CSV exigem UTF-8 sem controles binários. Office
valida estrutura ZIP sem extração, rejeita VBA/path traversal e volume expandido
excessivo. Essa inspeção **não é antivírus nem análise completa de documento**.

Limite default configurável: 20 MiB por anexo. O preview também tem limite de
28 MiB por request JSON/base64. Esses limites de recursos não encerram conversas.
Bytes ficam em quarentena sob hash do Scope e basename SHA-256.blob. Não há
download inline, execução, renderização de conteúdo ativo ou parser externo.
Tentativas de escapar o diretório e symlinks de destino são rejeitadas.
Metadata mantém nome, MIME real/declarado, tamanho, origem, status, digest e referência.
Anexo rejeitado não recebe mensagem nem metadata. Remover do composer apenas
desvincula; bytes já enviados podem ficar órfãos. Não há limpeza automática nesta
fundação, para evitar apagar dados silenciosamente.

Todo acesso ao storage exige owner/tenant/workspace. get_conversation, mensagem,
anexo, pesquisa, checkpoint, resumo e retrieval recusam identidade divergente.
A identidade é responsabilidade de um adaptador autenticado futuro; Scope não
substitui RBAC. Dados estão em claro no SQLite/arquivos locais: use diretório
privado protegido pelo sistema operacional; backup/criptografia são trabalho futuro.

Texto/metadata passam por redação de padrões conhecidos de credenciais antes de
persistir. Nunca enviar segredos. A redação não é DLP universal nem inspeciona
segredos dentro de PDFs/imagens/Office; o host de produção deverá implementar
a política de conteúdo necessária antes de aceitar anexos confidenciais.
Servidor não registra corpos nem tokens. API exige token aleatório de sessão,
Host loopback exato e Origin same-origin; CSP e textContent evitam conteúdo
ativo de mensagem. Não expor esse servidor na rede.

## Autorização e estados

READ_ONLY: explicar, consultar, verificar, analisar.
LOW_RISK: rascunho, relatório, criar contrato de tarefa.
REQUIRES_APPROVAL: publicar, email, merge, deploy, gasto, credenciais, abrir Trader.
BLOCKED: trading real e ações desconhecidas.

A classificação usa ação explícita do contrato; não tenta compreender livremente
a intenção em linguagem natural. Escolher READ_ONLY no browser não concede
autoridade. Um executor futuro deve reclassificar a ação real num domínio confiável
e aplicar gates existentes; nunca usar a classificação do browser como autorização.

PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED são contratos
de estado. A UI renderiza estados persistidos, incluindo aprovação pendente e
cancelamento. Enviando/concluído/erro/indisponível têm feedback real local.
Pensando/executando não são simulados: precisam de backend conectado. Não existe
botão de autorizar execução nem executor perigoso nesta versão. O futuro fluxo de
aprovação deverá usar recibos scoped do sistema existente.

Feedback cria evento ligado à mensagem; timestamps são UTC no storage e localizados
na UI. O composer permite texto multiline, imagem/arquivo e contrato na mesma
mensagem. Sidebar vira drawer em 390px, composer permanece acessível, layout sem
overflow horizontal, bordas violeta/ciano, alto contraste e reduced-motion.

## Executar e validar

Python 3.11+; runtime do chat usa apenas a biblioteca padrão.

    python atlasquant_aion_chat_ui.py --data-dir C:\private\aion-chat
    # Abrir http://127.0.0.1:8765

Não usar a árvore do repositório como diretório de dados de produção.
--attachment-max-bytes altera o limite de ingestão.

    python -m pytest test_atlasquant_aion_chat_foundation.py -q
    python -m pytest test_atlasquant_aion_chat_browser.py -q

Teste de browser exige dependência de desenvolvimento playwright e Chromium;
é separado para não adicionar dependência ao runtime. Se ausente, o módulo de
browser é skipped, o que **não** confirma validação visual. Nesta entrega foi
executado com Chromium real, desktop 1440x1000 e mobile 390x844. Cobre envio,
imagem/arquivo, XSS, reabertura, paginação, busca, arquivo, feedback, cancelamento,
checkpoint, overflow, drawer e reduced-motion. Artefatos PNG ficam fora do commit.

Os testes da fundação cobrem também isolamento, cursores, redaction, anexo
malicioso, validação de assinaturas, 1.000 mensagens, correções, pendências,
tarefas terminadas e orçamento técnico com reidratação.

## Integração futura

1. Montar Scope a partir da identidade autenticada existente, nunca do cliente.
2. Injetar AionChatStore e adapter de modelos na aba do AION numa PR separada.
3. Preparar contexto, contar tokens e reidratar lacunas antes de decisões.
4. Salvar respostas reais como assistant com provenance/truth_state.
5. Extrair eventos estruturados com evidência e aprovação de correções.
6. Preparar export de namespace para CheckpointMasterAdapter; salvar remotamente
   somente com o gate/recibo oficial. Esta versão não faz save remoto.
7. AION Core, Biblioteca, English, Negócios e Investimentos usam RetrievalAdapter/
   ModelAdapter com o mesmo Scope. Trading/ferramentas usam TaskAdapter com gates
   reais e jamais ganham autoridade do chat.
8. VoiceAdapter transcreve para Message.user e usa a resposta do mesmo histórico.
   Disponibilidade/quota/retomada de voz precisam de implementação de provedor.
9. Antes de produção: autenticação, criptografia/backup, isolamento operacional,
   migração de schema, proteção DLP, busca escalável, transação conjunta da
   compactação e streaming de respostas; o servidor loopback não é o serviço final.

Nenhum deploy, merge, alteração da main ou auto-merge faz parte desta entrega.
