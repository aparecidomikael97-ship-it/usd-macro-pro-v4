# AION B2B — Terminal Certificate Reference UI Draft V1

Status: **Draft-only / read-only / fail-closed / no live binding**.

## Objetivo

Integrar o componente estático do Terminal Execution Certificate na interface de
referência do AtlasQuant sem conectar ainda qualquer estado real de produção.

## Local

A integração aparece somente em:

**Negócios → Auditoria / LGPD**

Nenhum outro módulo recebe o painel.

## Entrada segura

A Reference UI recebe somente o
`terminal_certificate_panel_view_model`.

Ela não aceita HTML bruto como argumento.

O próprio renderer chama
`render_terminal_certificate_panel_offline(...)`, que revalida o view-model,
escapa conteúdo e recusa qualquer autoridade/controle indevido.

## Fail-closed

Se o view-model for inválido:

- nenhum digest/certificado é publicado;
- nenhum estado VERIFIED é inferido;
- a UI mostra apenas uma mensagem de evidência indisponível/fail-closed.

## Sem live binding

Nesta etapa `render_reference_workspace(...)` **não lê**
terminal certificate de `st.session_state`.

Portanto o caminho usado pela aplicação real continua inalterado.

A integração só é exercitada quando `reference_html(...)` recebe o view-model
explicitamente em teste/revisão Draft.

## Visual

O componente recebe estilo estático e responsivo coerente com o cockpit:

- grid de duas colunas no desktop;
- uma coluna em telas menores;
- digests com quebra segura;
- badge de estado;
- aviso explícito de evidência sem autoridade.

## Autoridade

O painel continua sem execução, retry, reopen, reconciliação, rollback,
compensação, billing, CRM, provisionamento, deploy ou mutação de produção.

## Próximo limite

Depois da certificação desta Draft, o próximo passo deverá ser definido
explicitamente. Nenhum live/session binding ou deploy fica autorizado por esta
integração.
