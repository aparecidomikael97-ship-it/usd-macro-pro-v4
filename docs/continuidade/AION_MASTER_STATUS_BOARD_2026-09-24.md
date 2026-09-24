# AtlasQuant — AION Painel Mestre de Estado — 2026-09-24

## Objetivo

Consolidar em uma única visão administrativa os estados que antes apareciam espalhados entre memória, Secretaria, feature flags e contratos externos.

O painel não executa ações. Ele apenas classifica evidências fornecidas pela execução atual.

## Estados permitidos

### CONFIRMED

Só pode ser usado quando a execução atual fornece evidência explícita suficiente.

Exemplo:

- o processo informa um source build;
- o contexto marca a informação como confirmada;
- o runtime do Checkpoint Mestre retorna status confirmado;
- um conector externo fornece confirmação explícita.

### BLOCKED

Usado para proteção deliberada, por exemplo:

- feature flag desligada;
- trading real bloqueado;
- alterações locais ainda não persistidas;
- fila aguardando aprovação.

Bloqueado não significa erro. Muitas vezes significa que o Guardian está funcionando.

### EXTERNAL_DEPENDENCY

Usado quando a capacidade foi habilitada, mas ainda falta prova externa.

Exemplos:

- rede social;
- marketplace;
- pagamento;
- promoção;
- entitlement;
- deploy de produção.

Feature flag ligada nunca é tratada como prova de integração.

### UNKNOWN

Usado quando a execução simplesmente não tem evidência suficiente.

Ausência de evidência não é convertida em sucesso nem em falha inventada.

## Itens consolidados

O painel atual acompanha:

- runtime do aplicativo;
- Checkpoint Mestre do runtime;
- alterações locais ainda não persistidas;
- frescor da leitura de mercado;
- IA externa;
- publicação social;
- publicação em marketplace;
- pedidos de marketplace;
- pagamento/assinatura;
- ativação de promoções;
- ativação de entitlements;
- deploy de produção;
- trading real;
- fila de aprovações;
- presença do registro local de entitlements.

## Separação importante

O item **Runtime do aplicativo** confirma somente o build informado pelo processo que está executando o AION.

Ele não substitui uma prova independente de que o Render está rodando o commit mais recente da main.

Portanto:

- build informado pelo processo != prova de paridade com main;
- HTTP 200 != prova de paridade com main;
- feature flag ligada != integração confirmada;
- pagamento recebido != entitlement concedido;
- score de mercado != probabilidade de lucro.

## Central AION

A Central passa a mostrar quatro contadores:

- Confirmados;
- Bloqueados;
- Dependência externa;
- Desconhecidos.

Também mostra a tabela completa com:

- área;
- item;
- estado;
- detalhe;
- próxima ação.

## Secretaria AION

A Secretaria recebe a lista de pendências do Painel Mestre.

Ela pode explicar a próxima ação, mas não transforma a pendência em ação automática.

## Segurança

O módulo:

- não chama GitHub;
- não chama Render;
- não chama OpenAI;
- não chama pagamento;
- não chama redes sociais;
- não chama marketplaces;
- não chama corretora;
- não grava secrets;
- não executa deploy;
- não altera usuário;
- não altera role;
- não ativa trading real.

## Estado deste bloco

- contrato do Painel Mestre: implementado em código;
- integração Central AION: implementada em código;
- integração Secretaria AION: implementada em código;
- testes fail-closed: implementados;
- execução externa automática: inexistente;
- trading real: bloqueado.
