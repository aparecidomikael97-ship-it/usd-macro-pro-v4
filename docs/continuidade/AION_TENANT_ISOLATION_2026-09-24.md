# AtlasQuant — Isolamento do AION por assinante — 2026-09-24

## Objetivo

Preparar o futuro **Meu AION** para clientes/assinantes sem transformar o AION oficial do administrador em um assistente compartilhado.

A regra central é:

**AION ADMIN e AION pessoal são contextos diferentes, com memória, permissões e namespaces separados.**

## Estado atual

Este bloco cria apenas a fundação de isolamento.

O **Meu AION ainda não é exibido ao assinante**.

Nenhum cliente recebe automaticamente:

- acesso ao AION;
- memória pessoal persistente;
- modelo externo;
- cobrança;
- publicação;
- permissão administrativa;
- trading real.

## Elegibilidade

Um futuro AION pessoal só pode ser considerado elegível quando houver simultaneamente:

1. sessão autenticada válida;
2. perfil USER ou SALES;
3. credencial válida com fingerprint;
4. entitlement de escopo exato:
   `AION_PERSONAL`;
5. entitlement em estado efetivo e confirmado por evidência externa.

Login sozinho não concede AION pessoal.

Perfil USER/SALES sozinho não concede AION pessoal.

Pagamento sozinho não concede AION pessoal.

Cupom sozinho não concede AION pessoal.

## Namespace por credencial

Cada sessão elegível recebe um identificador opaco derivado de:

- username normalizado;
- fingerprint da credencial.

Formato lógico:

`tenant/<opaque-id>`

Caminho futuro de runtime:

`dados/aion/tenants/<opaque-id>/checkpoint.json`

A credencial faz parte do namespace por segurança.

Se a senha/credencial for rotacionada, o namespace muda. Isso evita que uma credencial nova herde silenciosamente memória antiga.

Em uma fase futura, um identificador imutável de conta poderá substituir esse mecanismo mediante migração explícita e auditada.

## Memória

A memória inicial de um tenant contém somente informações próprias e permitidas:

- preferências;
- progresso da Academy;
- watchlist;
- notas pessoais com estado de verdade.

Ela não herda:

- Checkpoint Mestre do ADMIN;
- documentos canônicos privados do projeto;
- tarefas administrativas;
- Studio;
- Negócios;
- Desenvolvimento;
- Promoções;
- segredos;
- memória de outro usuário.

## Domínios permitidos

O contrato inicial permite somente:

- central;
- trading;
- academy;
- support;
- account.

Domínios administrativos continuam fora do tenant:

- secretary;
- studio;
- business;
- laboratory;
- development;
- promotions;
- admin.

Isso poderá ser ampliado no futuro somente por decisão explícita e testes.

## Ações locais permitidas

O contrato aceita apenas ações locais de baixo risco, como:

- leitura de mercado já disponibilizada ao usuário;
- explicação de indicadores;
- ajuda de Academy;
- ajuda de suporte;
- leitura da própria conta;
- salvamento de preferências próprias.

Ações externas/administrativas permanecem bloqueadas.

Exemplos bloqueados:

- ler memória ADMIN;
- ler outro tenant;
- administrar usuários;
- aprovar custo;
- publicar em redes sociais;
- publicar marketplace;
- ativar promoção;
- ativar entitlement;
- cobrar cliente;
- deploy;
- merge;
- ler/escrever segredos;
- trading real.

## Cross-tenant

A regra é fail-closed.

Um tenant só pode acessar o próprio `tenant_id`.

Qualquer outro ID retorna acesso negado.

Se uma memória recebida tiver `tenant_id` diferente, o conteúdo estrangeiro é descartado e um seed limpo do tenant atual é usado.

## Modelo externo

O contrato do tenant define:

`external_provider_enabled_by_default=false`

Ou seja, nenhum futuro assinante herdará automaticamente o provedor externo configurado para o administrador.

Qualquer uso futuro de IA externa precisará de política própria de custo, privacidade e autorização.

## Trading

O contrato mantém:

`real_trading_enabled=false`

O AION pessoal não pode executar ordens reais.

Ele poderá futuramente explicar mercado, acompanhar watchlist e apoiar aprendizado, mas não ultrapassa os gates operacionais.

## Painel ADMIN

A aba **Assinaturas & Promoções** agora mostra uma área:

**AION pessoal · isolamento por assinante**

Ela informa:

- quantos entitlements `AION_PERSONAL` existem;
- quantos estão ativos confirmados;
- cross-tenant bloqueado;
- memória ADMIN não herdada;
- documentos privados não herdados;
- modelo externo automático desligado;
- cobrança automática desligada;
- trading real bloqueado.

## Próxima fase

Depois que esta fundação estiver validada e o Render reconciliado, a próxima evolução poderá ser:

1. criar o shell visual do **Meu AION**;
2. resolver entitlement do usuário de forma server-side;
3. carregar apenas a memória do namespace daquele tenant;
4. impedir qualquer fallback para memória ADMIN;
5. permitir somente capacidades do contrato pessoal;
6. adicionar persistência própria com concorrência/rollback;
7. testar revogação e rotação de credencial.

## Regra da verdade deste bloco

- isolamento por tenant em código: IMPLEMENTADO;
- testes de cross-tenant: IMPLEMENTADOS;
- entitlement `AION_PERSONAL`: EXIGIDO PELO CONTRATO;
- painel ADMIN de prontidão: IMPLEMENTADO EM CÓDIGO;
- AION pessoal visível ao assinante: NÃO;
- memória pessoal persistida em produção: NÃO CONFIRMADA / NÃO ATIVADA;
- provedor externo para assinante: DESLIGADO;
- cobrança automática: DESLIGADA;
- trading real: BLOQUEADO.
