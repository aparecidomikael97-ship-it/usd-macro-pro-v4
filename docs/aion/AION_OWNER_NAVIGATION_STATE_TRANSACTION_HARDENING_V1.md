# AION — Navegação do proprietário com estado temporário e falha fechada V1

**08/10/2026 · PR Draft · exclusivamente teste e código no GitHub. Sem integração com Streamlit de produção, PC, celular ou deploy.**

## Falha concreta encontrada

A cadeia protegida da PR #1084 anteriormente chamava a navegação interna passando o mesmo dicionário `session_state` ao roteador. O roteador central pode gravar `atlasquant_central_choice` e pedidos de navegação e depois encontrar uma exceção. Mesmo quando o retorno indicava `BLOCKED`, o estado já poderia ter sido modificado. Isso é **um problema de atomicidade de estado**, e não deve ser confundido com prova de execução do comando.

## Correção isolada

1. A função `request_rooted_owner_navigation` agora exige um **dicionário Python puro**. Rejeita objetos `MutableMapping` genéricos, incluindo proxies Streamlit, antes de qualquer escrita. Um host real necessitará de um adaptador transacional próprio, posteriormente autorizado.
2. O modo atual de experiência é copiado como string simples para uma área **temporária** de navegação. Nenhum outro objeto, segredo, token, conversa ou referência mutável da sessão é passado ao roteador.
3. A cadeia criptográfica preexistente ainda valida registro raiz, chave ativa, dispositivo, prova da sessão e assinatura da intenção exata. O nonce pode ser consumido no processo; falhas sempre exigem nova prova.
4. O roteador muta apenas o dicionário temporário. Em caso de erro, rejeição do roteador, chave adicional, mudança do modo, alvo diferente ou pedido de execução indevido, o **estado original permanece inalterado**.
5. Somente no sucesso, os campos de navegação previamente revisados são gravados de uma só vez no dict do laboratório:
   - `atlasquant_central_choice`
   - `atlasquant_guided_revalidation_request` quando o destino exigir
   - `aion_admin_workspace_jump` exclusivamente para Negócios.
6. Os destinos e tipos de solicitação são explicitamente conferidos. `executes_action` e `real_orders_enabled` devem ser **False**. Não há autorização para abrir apps externos, executar comandos do Windows, ordens, compras ou deploy.

## Cobertura dos testes

36 cenários anteriores da PR #1084, mais **14 testes novos**, totalizando **50 testes independentes** e subtestes. Entre os novos: rotas legítimas Trader/Negócios/Investimentos/AION/central, preservação de estado privado, exceção após escrita parcial, falha tratada após escrita, injeção de campo inesperado, tentativa de marcar execução, troca de alvo, mudança de modo e rejeição de proxies/dados não confiáveis.

Os testes devem rodar em Windows e Linux usando o workflow já existente `aion-rooted-owner-signed-ui-preflight-v1.yml` e também passar pelo gate de importações da #1085, sem merge nem deploy.

## Limites de garantia

- `dict.update` em memória do processo de teste **não é transação durável de banco de dados**, nem garante atomicidade se o host real usar um proxy com efeitos externos, conexões, threads concorrentes ou armazenamento distribuído.
- Não resolve XSS, CSRF, autenticação real, raiz inscrita, chave protegida por FIDO2/Windows Hello, contador monotônico antirrollback, custódia de chaves ou dispositivo físico.
- Não confirma tela aberta, voz, wakeword ou execução real. Retorno `INTERNAL_NAVIGATION_REQUESTED` é um registro de solicitação.
- O roteador comum por botões do AtlasQuant é mantido; a barreira vale apenas para a **rota protegida do HUMAN_OWNER**. Não foi integrada à UI real.
- A auditoria de imports (#1085) é auxiliar e não substitui fronteiras de confiança em processos separados.

**Gate futuro obrigatório:** ao chegar no PC, um host autenticado e separado deverá registrar snapshot de sessão, checar identidade, aplicar o plano de navegação em transação protegida e confirmar o estado de UI. Isso depende de revisão de segurança e autorização explícita antes de qualquer ativação.

Sem merge, sem Render/Worker, sem acesso ao PC e sem despesa nova. O limite de infraestrutura temporário de R$ 200 mensais não muda.
