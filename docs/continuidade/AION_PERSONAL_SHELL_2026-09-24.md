# AtlasQuant — Meu AION — Shell lógico seguro — 2026-09-24

## Objetivo

Criar o estado lógico do futuro **Meu AION** antes de colocar qualquer aba, botão ou assistente visível para assinantes.

A interface pública **não é ativada neste bloco**.

O shell só organiza estados, capacidades, memória própria e regras de verdade.

## Estados

### LOCKED_AUTH

Não existe uma sessão autenticada USER/SALES válida para tenant.

O AION pessoal permanece indisponível.

### LOCKED_ENTITLEMENT

A sessão é válida, mas não há entitlement efetivo e confirmado de escopo:

`AION_PERSONAL`

Login sozinho não concede o assistente.

### READY_LOCAL

A identidade do tenant e o entitlement estão confirmados.

Mesmo nesse estado:

- modelo externo = DESLIGADO;
- publicação externa = BLOQUEADA;
- billing = BLOQUEADO;
- administração = BLOQUEADA;
- trading real = BLOQUEADO;
- persistência em produção = NÃO CONFIRMADA;
- UI do assinante = NÃO EXPOSTA.

## Rotas permitidas

O roteador pessoal só trabalha com:

- central;
- trading;
- academy;
- support;
- account.

Ele nunca roteia para:

- Development;
- Studio administrativo;
- Negócios administrativo;
- Promoções;
- Secretaria do administrador;
- segredos;
- deploy.

## Mercado

O shell só marca mercado como:

`CONFIRMED`

quando recebe simultaneamente:

- `fresh_confirmed=true`;
- resumo não vazio.

Caso contrário, o estado é:

`UNKNOWN`

e o shell não repete um resumo antigo como se fosse atual.

## Memória

Memória fornecida só é usada quando o `tenant_id` corresponde exatamente ao tenant autenticado.

Se a memória for:

- de outro tenant;
- sem tenant_id;
- incompatível;

ela é rejeitada para o shell e substituída por um seed efêmero limpo.

O estado registra:

`input_memory_rejected=true`

Nenhum conteúdo estrangeiro é herdado.

## Prompt packet futuro

O shell pode preparar um pacote de contexto local para uma futura inteligência.

Esse pacote:

- usa apenas memória própria sanitizada;
- inclui a verdade do mercado;
- contém regras explícitas contra invenção;
- bloqueia ADMIN memory;
- bloqueia project docs;
- bloqueia outro tenant;
- bloqueia billing;
- bloqueia deploy;
- bloqueia trading real.

E, nesta versão:

`executes_provider_call=false`

## Persistência

O shell consulta apenas o contrato de persistência.

Mesmo quando o plano de load está elegível:

- `network_io_implemented=false`;
- `persistence_confirmed=false`.

Isso evita chamar memória efêmera de memória salva.

## Estado de verdade deste bloco

- shell lógico: IMPLEMENTADO EM CÓDIGO;
- roteamento pessoal: IMPLEMENTADO EM CÓDIGO;
- matriz de capacidades: IMPLEMENTADA EM CÓDIGO;
- filtro de mercado fresco: IMPLEMENTADO EM CÓDIGO;
- rejeição de memória estrangeira: IMPLEMENTADA EM CÓDIGO;
- prompt packet local: IMPLEMENTADO EM CÓDIGO;
- chamada de IA externa: NÃO IMPLEMENTADA;
- UI Meu AION para assinante: NÃO EXPOSTA;
- persistência pessoal em produção: NÃO CONFIRMADA;
- cobrança automática: DESLIGADA;
- trading real: BLOQUEADO.
