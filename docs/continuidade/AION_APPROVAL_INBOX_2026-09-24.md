# AtlasQuant — AION Central de Aprovações — 2026-09-24

## Objetivo

Criar uma única visão administrativa das decisões que realmente chegaram ao estágio de aprovação.

A Central de Aprovações não transforma visibilidade em autorização.

Ela apenas reúne itens que já estão em um estado explícito de revisão.

## O que entra na fila

### Tarefas

Entram quando:

- status = WAITING_APPROVAL; ou
- approval.required = true;
- e approval.approved = false.

### Studio

Entram somente quando:

- status = REVIEW;
- e ainda não houve aprovação do ADMIN.

Projetos em IDEA ou SCRIPT não são inventados como pendência.

### Negócios

Entram somente quando:

- status = VALIDATE;
- e ainda não houve aprovação do ADMIN.

Produtos em RESEARCH não são chamados de aprovação pendente.

### Promoções

Campanhas em DRAFT e não aprovadas aparecem na fila.

Isso não significa que a campanha esteja ativa.

### Entitlements

Solicitações em DRAFT e não aprovadas aparecem na fila.

A aprovação continua sem alterar:

- conta;
- role USER/SALES/ADMIN;
- pagamento;
- acesso efetivo;
- trading.

## Ordem

A caixa organiza os itens por:

1. prioridade P0 → P3;
2. tipo;
3. data de criação;
4. identificador.

Itens de tarefa podem preservar a prioridade original.

Promoções e entitlements entram como P1 porque envolvem efeitos comerciais futuros, embora nenhuma ação externa seja executada.

Studio e Negócios entram como P2.

## Interface

A Central AION passa a mostrar:

- total pendente;
- quantidade P0;
- quantidade P1;
- quantidade de tarefas;
- tabela com prioridade, tipo, área, status, item e motivo.

A Secretaria AION também mostra quantas decisões estão pendentes.

## Regra de execução

Nesta versão:

- não existe botão central de “aprovar tudo”;
- não existe aprovação automática;
- não existe execução automática depois da aprovação;
- a decisão é feita na área de origem;
- cada área continua usando seu próprio contrato de segurança.

Essa separação evita que uma fila administrativa se transforme acidentalmente em um bypass do Guardian.

## Segurança

O agregador:

- não chama rede;
- não chama GitHub;
- não chama Render;
- não chama pagamento;
- não chama redes sociais;
- não chama marketplace;
- não altera conta;
- não altera role;
- não ativa promoção;
- não ativa entitlement;
- não publica conteúdo;
- não publica produto;
- não executa trading real.

## Estado deste bloco

- agregador unificado: implementado em código;
- integração Central: implementada em código;
- integração Secretaria: implementada em código;
- aprovação automática: bloqueada;
- ações externas: não executadas;
- trading real: bloqueado.
