# AtlasQuant — AION Promoções + Entitlements — 2026-09-23

## Objetivo

Transformar a aba Promoções do AION em um workspace persistente, seguro e auditável para:

- 7 dias grátis;
- 30 dias grátis;
- outros períodos de teste;
- desconto percentual;
- desconto fixo;
- limite de usos;
- janela de validade;
- aprovação administrativa;
- integração futura com assinatura/acesso.

## Regra de segurança dos códigos

Ao criar uma campanha:

1. o código público é gerado com fonte criptograficamente segura;
2. o código completo aparece apenas na sessão de criação;
3. o Checkpoint Mestre não armazena o código em texto puro;
4. o Checkpoint guarda somente SHA-256 + últimos 4 caracteres;
5. se o administrador perder o texto do código, a orientação é criar outra campanha/código.

Isso reduz exposição acidental de códigos promocionais no histórico.

## Status de campanha

- DRAFT
- APPROVED
- PROVIDER_READY
- ACTIVE
- DISABLED
- EXPIRED

O status `ACTIVE` é reservado para evidência confirmada de um provedor/registro real.

A tela do AION não pode transformar um rascunho em acesso real apenas por mudar um campo local.

## Aprovação e Guardian

Aprovar uma campanha:

- registra a aprovação do ADMIN;
- não concede assinatura;
- não ativa acesso;
- não chama provedor externo.

O preflight de ativação exige:

- campanha aprovada;
- sessão ADMIN;
- feature flag `promotion_activation`;
- aprovação explícita da ação;
- Guardian.

Mesmo com o preflight elegível, `executes_activation=false`.

## Resgate

O contrato de resgate verifica:

- código;
- status ativo;
- início;
- expiração;
- limite de usos.

O preflight nunca concede entitlement sozinho.

Um resgate só pode ser registrado como concedido quando um futuro provedor/registro de assinaturas devolver evidência concreta e confirmada.

## Checkpoint Mestre v4

A memória passa a incluir:

`promotions.campaigns`

`promotions.redemptions`

`promotions.digest`

Além dos blocos já existentes:

- operating;
- studio;
- business.

Checkpoints antigos são migrados apenas em memória até o administrador salvar explicitamente no runtime.

## Interface

A aba Promoções passa a mostrar:

- número de campanhas;
- aprovadas;
- ativas confirmadas;
- resgates confirmados;
- criação de campanha;
- benefício;
- limite de usos;
- início/expiração;
- código em exibição única da sessão;
- tabela com código mascarado;
- aprovação;
- estado do preflight comercial.

## O que continua desligado

- criação automática de usuário;
- extensão automática de assinatura;
- pagamento;
- cobrança;
- ativação real de código;
- alteração automática de permissões;
- trading real.

## Próxima integração futura

Quando houver registro comercial/assinaturas conectado, o AION poderá:

1. enviar uma campanha aprovada ao provedor;
2. receber ID externo;
3. marcar ACTIVE apenas com evidência;
4. validar resgate;
5. receber confirmação de entitlement;
6. registrar auditoria.

Nenhuma dessas etapas deve ser descrita como ativa antes da integração real.
