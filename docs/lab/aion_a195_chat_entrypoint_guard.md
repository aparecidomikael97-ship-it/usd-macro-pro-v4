# AION A195 — revalidação da identidade da sessão Streamlit no ENTRypoint real de Chat

Data: 27/10/2026 · **PR Draft sem merge/deploy** · 0/6 P0 homologadas, **HARD NO-GO**.

## Por que existe?

Na base atual, o login principal `atlasquant_access_panel.render_access_gate` valida
sessão e cadastro. Porém os wrappers Streamlit `build_streamlit_staged_binding`
e `build_streamlit_production_binding` recebiam um objeto `access` injetado
pelo chamador e só conferiam seu formato e campos. Um dicionário sintético
com `allowed=True, mode=AUTHENTICATED, role=ADMIN, fingerprint=qualquer`
podia satisfazer `validate_product_binding` se um host inseguro o passasse.
Isso mostra **suposição sobre o host**, NÃO demonstra bypass remoto do login real.

## Correção PROPOSTA para revisão

Arquivo novo `atlasquant_aion_chat_entrypoint_guard.py` contém o gate puro
`require_chat_host_session(st, access)`. Cada wrapper Streamlit de chat,
**somente quando sua flag específica está ativada**, executa o gate antes
de abrir/reutilizar SQLite ou construir a conexão PostgreSQL. O gate:

- Obtém a sessão por **`st.session_state["atlasquant_access_session"]`**,
  não de `access.session` ou dados do prompt.
- Carrega o cadastro de `ATLASQUANT_USERS_JSON` com a mesma precedência
  Streamlit secrets → environment do login do app, sem expor hashes.
- Exige `session_is_current` (cadastro atual, active, role e fingerprint),
  ADMIN e permissões esperadas pelo cadastro, e igualdade completa
  `access.session` ↔ sessão corrente do servidor.
- Valida presença e intervalo finito de `authenticated_at` e `last_seen`;
  aplica limite absoluto de 12 h e inatividade de 2 h, como no login.
- Em qualquer falha lança `PermissionError` com razão genérica;
  não cria store, não troca tenant, não faz fallback para OPEN.
- Quando a flag de chat está OFF retorna `None` sem carregar/abrir banco.

O `build_staged_host_binding` genérico e o `build_production_host_binding`
continuam exigindo origem autenticada por contrato; wrappers são a superfície
real usada pela shell Streamlit. **A proteção de outros chamadores genéricos,
endpoints HTTP e hosts fora de Streamlit ainda exige inspeção.**

## Limites graves que NÃO foram resolvidos

O cadastro e a sessão dentro do processo Streamlit **não são uma raiz de
confiança externa, assinatura independente ou prova de inscrição HUMAN_OWNER**.
Se o processo, secrets ou session_state forem comprometidos, o guard não
garante identidade. `Scope` no SQLite também continua livremente forjável
por código com acesso direto ao handle. Sem fixar raiz externa, CAS
independente, intenção semântica durável e anti-rollback externo, G122
permanece RED em 5 provas por SO. Nenhuma P0 pode ser fechada a partir
de testes locais. A auditoria de dependências de `main` segue com falhas
conhecidas herdadas até merge/validação separados.

## Testes dedicados

`python -B -m unittest -v labs.test_a195_chat_entrypoint_guard`

Ensaio com cadastro e sessão 100% sintéticos sobre funções reais
`atlasquant_access_control` e função real do guard. AST compila as
**funções originais dos wrappers Streamlit** e substitui **somente** o
construtor externo do banco por stub (não conecta PostgreSQL/SQLite real).
Nega role e access falsos, sessões inativas/revogadas, troca de senha,
timestamp inválido, login expirado, permissões modificadas, falha em
secrets e indisponibilidade do cadastro. Ubuntu + Windows, sem deps extras.

## Decisões do proprietário

Negócios congelado em 27/10: sem novas implementações/comercialização B2B.
Prioridade no núcleo AION, Trader, Investimentos. **Sem novos gastos até
05/11/2026**. A partir de 06/11 somente reavaliar, sem contratação automática.
Sem AWS, novos serviços, envio SEND, Worker, trades reais, cobrança ou deploy.
