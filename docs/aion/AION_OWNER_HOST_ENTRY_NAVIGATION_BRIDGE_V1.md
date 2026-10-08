# AION — ponte de entrada do proprietário e navegação interna V1

Data: 08/10/2026. **Status: Draft; compatibilidade e testes de CI, sem ativação de produção.**

## Objetivo

Conectar os contratos de `atlasquant_aion_owner_experience_v1.py` à navegação já suportada por `atlasquant_central_hub_ui.py` e `atlasquant_navigation_bridge.py`, sem duplicar login, autenticação, sessão ou roteamento de área.

Após autenticação real como ADMIN **e** atestação independente de HUMAN_OWNER por host confiável, o AION pode preparar uma saudação contextual e atender ao comando de texto “AION, abre Trader” dentro da sessão autenticada. A mera condição ADMIN, o nome exibido, um campo enviado pelo cliente ou a palavra de ativação “AION” **não comprovam identidade de proprietário**.

## Interface de integração

`prepare_owner_host_entry(access, owner_assertion, trusted_host_owner=...)` devolve `OWNER_ENTRY_READY` com saudação em texto quando os gates declarados estão satisfeitos. Nunca fala, abre microfone ou cria sessão.

`route_owner_text_navigation(session_state, access, owner_assertion, trusted_host_owner=..., text=..., device=...)` aceita somente gramática fechada de comandos simples e encaminha para `request_central_destination`. A resposta `INTERNAL_NAVIGATION_REQUESTED` significa **solicitação de navegação, NÃO observação de uma tela aberta**. O host confirma o resultado em sua própria interface. Trader usa o Radar iniciante/avançado; Negócios, Investimentos e AION usam os bridges existentes.

**Limite de confiança obrigatório:** `trusted_host_owner=True` somente pode ser definido pelo host no servidor após autenticação/atestação verificadas fora deste módulo e vinculadas à sessão concreta. **Jamais** deve vir de formulário, URL, browser, localStorage, cookie manipulável ou campo `verified` enviado pelo cliente. `owner_assertion` verifica coerência de campos; **não verifica assinaturas criptográficas**. Antes de ligar esta ponte à interface real, será obrigatório construir o emissor/verificador autenticado e associá-lo à sessão correta. Até lá, a ponte permanece **desconectada/desabilitada** no host.

## Limitações, segurança e FinOps

- Nenhum comando eleva privilégios ADMIN/HUMAN_OWNER.
- Comandos múltiplos, ambíguos, de fornecedores externos ou de alto risco são rejeitados.
- “AION abre WhatsApp”, “AION abre ChatGPT”, “AION abre Spotify”, Pix, ordens, assinatura, arquivos e deploy não são executados nem enfileirados.
- O módulo não lê segredos e não chama fornecedores; modifica somente **estado de navegação interna** já existente na sessão confiável.
- Nenhum resultado afirma que a interface de destino realmente abriu.
- Sem instalação Windows, microfone, hotword real, voz contínua, persistência, merge, deploy, Worker ou Core V1 congelado.
- Nenhum custo novo. FinOps mantém limite provisório de **R$ 200/mês** e aumento somente após condições financeiras e aprovação expressa independente.

## Critérios para integração posterior

1. Testes Linux e Windows, incluindo identidade negada, host não confiável, injeção, estado de sessão, reuso do bridge e ausência de efeitos externos.
2. Revisar limite de confiança do host e a origem da atestação.
3. Montar no host autenticado real somente após disponibilizar prova independente de proprietário; observar a transição visual verdadeira.
4. Validar PC e celular no ambiente do proprietário, com autorização específica.

A aprovação de CI certifica o **contrato isolado**, não a autenticação externa, a UI final ou a execução física.
