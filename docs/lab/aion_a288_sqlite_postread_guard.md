# A288 — opt-in SQLiteChatStore post-read data_version guard (LAB)

**Status:** PROPOSTA DE LAB; **HARD NO-GO**; P0 homologados **0/6**;
**ZERO_AUTO_RESEND**; sem Worker, deploy, send, ordens ou serviço pago.

## Motivação

A287 identificou uma janela real entre o PRAGMA data_version verificado
em _require_open() e o SELECT subsequente nos métodos de leitura do chat.
Uma segunda conexão nativa podia fazer COMMIT nessa janela; o método
terminava e a alteração só era percebida por uma chamada de saúde posterior.

## Mudança

A288 mantém o padrão strict_local_data_version=False de A286: operações
normais de várias conexões/processos cooperativos não mudam.

Somente quando o proprietário do *LAB single-writer* usa
SQLiteChatStore(path, strict_local_data_version=True), uma segunda
verificação local após buscar o conteúdo SQL ocorre nos métodos:

- get_conversation;
- list_conversations (e search_conversations, que delega);
- list_messages;
- get_message;
- get_attachment;
- _latest (get_latest_checkpoint e get_latest_summary);
- retrieve_messages (inclusive com termo de busca vazio).

A segunda verificação executa a mesma _require_open() fail-closed da A286:
um COMMIT por outra conexão ou indisponibilidade do contador provoca
FAILED sticky antes de liberar o resultado. Nos casos de ausência de registro,
a verificação ocorre antes de devolver LookupError ou None.

## Contraprovas mantidas

- O experimento A287 no modo "pre-only historical negative control"
  desativa apenas o *novo helper* dentro da simulação: demonstra de modo
  reproduzível a falha anterior, sem desativar guardas normais em runtime.
- A287 comprova uma mudança após o *último* post-check: até a checagem
  posterior tem TOCTOU e não torna a operação atômica.
- A286 comprova que uma segunda conexão **cooperativa** também altera o
  contador. Por isso A288 não torna o modo estrito padrão.
- O contador SQLite não comprova qual FD/VFS nativo está aberto; não fornece
  raiz de confiança ou ordenação antirrollback fora da máquina e não percebe
  escritas da própria conexão.
- Resultado de COMMIT incerto, assinatura de dono, intenção semântica,
  recibo do provedor e marcador off-host continuam problemas independentes.

## Validação proposta

- 12 novos casos A288: seis endpoints após COMMIT intercalado, falso negativo
  histórico A287 mantido, writer padrão cooperativo, COMMIT próprio, campos
  attachment/checkpoint/search/empty retrieve, LookupError normal, leitura
  indisponível, janela final TOCTOU e zero autoridade externa.
- Regressões A287, A286, A285, chat/SQLite A233/A240/A245/A248/A249/A267,
  guarda de risco e simulador.
- Ubuntu e Windows via GitHub Actions executores padrão gratuitos para este
  repositório público. Nenhum contrato, Worker ou produção.
- Nunca considerar CI verde suficiente para homologar P0-5/P0-6.

**Decisão:** apenas um avanço local contra corrida de leitura, sem GO real.
