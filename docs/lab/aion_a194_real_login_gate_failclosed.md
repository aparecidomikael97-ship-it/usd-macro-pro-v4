# AION A194 — login da aplicação e fail-closed na ausência do módulo de acesso (LAB review)

27/10/2026 · Proposta em Draft, **sem merge, deploy ou custo**. 0/6 P0 homologadas, HARD NO-GO.

## Falhas concretas no caminho real do AtlasQuant

A inspeção da `usd_macro_pro_v4_cloud.py` mostrou:
1. O login do Streamlit é chamado antes do painel e do host AION. Quando
   `render_access_gate()` existe, o painel verifica a sessão contra
   `ATLASQUANT_USERS_JSON` com `session_is_current` e exige validade temporal.
   A produção normal portanto já possui uma barreira de sessão; não afirmar
   que um usuário remoto consegue forjar `Scope` nesse fluxo sem outra prova.
2. No **fallback de importação falha** do módulo de login, a aplicação
   anteriormente verificava somente `ATLASQUANT_AUTH_REQUIRED`. Com
   `ATLASQUANT_ENV=PRODUCTION` mas `ATLASQUANT_AUTH_REQUIRED=false`,
   o fallback entrava em modo OPEN. Proposta: exigir fechamento quando
   produção estiver marcada em segredos OU variável de ambiente, mesmo que
   a outra configuração diga false.
3. O helper real `atlasquant_access_panel.evaluate_access(required=True)`
   aceitava sessão com somente `{"role": "USER"}` quando chamado sem
   `users`. O shell real fornece `users` a partir do cadastro local, mas
   a interface de função permitia uma integração insegura. Proposta:
   `SESSION_REVOKED` quando não há `users` ou a sessão não é atual.

## Patch proposto

- `atlasquant_access_panel.py`: jamais declarar AUTHENTICATED sem cadastro
  explícito validando `session_is_current`.
- `usd_macro_pro_v4_cloud.py`: import falho + PROD explícito → st.stop();
  import falho + auth-required true → st.stop(); local OPEN continua OPEN.
- Corrigir o teste legado que exigia autorização por role isolada, antes
  de adicionar ampla regressão nova.
- Teste novo AST de fonte **exata** das duas funções/blocos reais. Compila e
  executa somente o bloco do fallback com objetos Streamlit simulados; não
  importa nem executa o app, não conecta serviços externos.
- Teste adversarial adicional aponta condição *ainda não resolvida*:
  `validate_product_binding` confia na origem da decisão do host;
  um dict com "authenticated" não constitui sozinho assinatura ou raiz de
  confiança externa.

## Riscos que persistem

- A fonte da sessão e do cadastro precisa ser provada em operação real,
  incluindo revogação, isolamento multiusuário, cookies e controle de processo.
- Entrada Python de baixo nível pode criar Scope forjado; essa PR não altera
  `SQLiteChatStore`, não supre prova de custódia independente nem protege
  histórico contra rollback conjunto.
- G122 e as seis P0 seguem RED; testes locais verdes não homologam operação real.
- Base `main` ainda tem falhas herdadas de auditoria de dependências; manter
  resultado global como FAIL enquanto não corrigidas.

## Limites financeiros / de produto

Negócios congelado por decisão do proprietário em 27/10; sem novas tarefas B2B.
Sem nova despesa até 05/11/2026; a partir de 06/11 apenas reavaliar mediante
nova aprovação expressa. Nenhum AWS/KMS/Worker, nenhuma ordem de mercado,
contato com clientes, SEND, merge, deploy ou faturamento.
