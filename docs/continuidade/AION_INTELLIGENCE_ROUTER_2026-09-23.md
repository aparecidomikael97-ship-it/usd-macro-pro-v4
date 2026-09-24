# AtlasQuant — AION Intelligence Router — 2026-09-23

## Objetivo

Preparar o AION para, no futuro, escolher entre uma rota local, uma rota externa rápida e uma rota externa de raciocínio, sem ativar nenhum provedor pago automaticamente.

## Regras

O roteador é apenas um planejador nesta fase.

Ele:

- classifica a complexidade;
- detecta sinais de conteúdo sensível;
- lê a feature flag do modelo externo;
- lê o estado real do cliente/provedor;
- lê o teto mensal aprovado;
- verifica o saldo;
- exige aprovação explícita de cada solicitação paga;
- decide uma rota elegível;
- **não chama nenhum provedor**;
- **não gera cobrança**.

## Rotas

- `LOCAL_DETERMINISTIC`
- `EXTERNAL_FAST`
- `EXTERNAL_REASONING`

Como o cliente externo ainda não está implementado/confirmado, o sistema atual continua na rota local.

## Privacidade

Conteúdo com sinais de senha, token, segredo, credencial, chave de API ou dados financeiros/pessoais sensíveis permanece local nesta fundação.

## Orçamento

O administrador passa a ter, no Laboratório:

- teto mensal máximo em USD;
- opção de permitir ou não solicitações pagas;
- saldo aprovado;
- estado do provedor;
- teste do roteador.

Salvar um teto:

- não cobra;
- não contrata;
- não habilita um cliente externo;
- não remove a aprovação por solicitação;
- não altera o bloqueio de trading real.

## Regra Custo Zero

O padrão continua:

- `allow_paid = false`;
- teto mensal = US$ 0;
- provedor externo desligado;
- nenhuma cobrança automática.

## Próxima etapa futura

Depois deste contrato estar validado, um cliente externo real pode ser implementado atrás de:

1. feature flag;
2. configuração segura do provedor;
3. confirmação de privacidade;
4. orçamento;
5. aprovação explícita;
6. observabilidade/auditoria;
7. fallback local.

Nenhuma dessas etapas deve ser descrita como ativa antes de evidência real.
