# AtlasQuant — Operação ADMIN / SALES

Este guia descreve o fluxo atual de contas e vendas. Ele não autoriza merge para main, publicação comercial, alteração automática de Secrets, broker ou ordens reais.

## ADMIN

O perfil ADMIN pode:

- visualizar contadores de USER / SALES / ADMIN ativos;
- criar uma proposta de nova conta;
- alterar perfil de uma conta;
- ativar/desativar uma conta;
- redefinir senha;
- revisar o diff antes da exportação;
- baixar um novo `ATLASQUANT_USERS_JSON` completo.

O portal **não grava** o Secret automaticamente. A atualização continua sendo uma operação manual/revisável.

Remoção destrutiva de conta é bloqueada pelo módulo de registro. Para encerrar acesso, a operação suportada é desativar a conta.

Alterar perfil, senha ou status invalida a sessão antiga porque a sessão é vinculada ao fingerprint atual da credencial.

## SALES

O perfil SALES pode:

- acessar o Portal Comercial;
- visualizar o fluxo de onboarding;
- conferir a situação de instalação/PWA;
- conferir o que está pronto e o que ainda está pendente antes da venda.

O perfil SALES não pode:

- criar/alterar usuários;
- alterar Secrets;
- habilitar broker;
- ativar ordens reais;
- alterar pesos/gates/estratégias;
- marcar Academy, voz, pagamentos, lojas nativas ou guia de corretoras como prontos antes da implementação real.

## USER

O perfil USER acessa o aplicativo, mas não recebe privilégios ADMIN ou SALES.

## Fluxo seguro de criação de conta

1. ADMIN entra no AtlasQuant.
2. Abre **Conta → Administração de Contas → Criar conta**.
3. Informa usuário, perfil e senha temporária forte.
4. O AtlasQuant gera um registro completo revisado.
5. ADMIN revisa o diff.
6. ADMIN baixa o JSON.
7. O Secret `ATLASQUANT_USERS_JSON` é atualizado manualmente no ambiente.
8. Após restart/redeploy, a conta passa a usar a configuração nova.

## Fluxo seguro de alteração

1. ADMIN seleciona a conta.
2. Escolhe alterar perfil, ativar/desativar ou redefinir senha.
3. O AtlasQuant gera uma proposta completa.
4. O diff mostra os campos alterados.
5. Nenhuma remoção destrutiva é permitida.
6. A alteração só entra em vigor depois da atualização manual do Secret.

## Estado comercial

A PWA pode ser usada em Android, iPhone/iPad, Windows, macOS e Linux via navegador compatível.

Ainda permanecem separados e pendentes para uma venda pública completa:

- Academy/vídeos;
- assistente de voz;
- guia final de corretoras/plataformas;
- termos/política de privacidade/riscos;
- licenciamento comercial de dados;
- pagamentos/assinatura;
- publicação Google Play;
- publicação Apple App Store.

## Segurança de trading

Conta comercial não muda o motor operacional.

Permanecem desligados:

- `real_orders=false`;
- `broker_connection=false`;
- `automatic_gate_change=false`;
- `automatic_promotion=false`.
