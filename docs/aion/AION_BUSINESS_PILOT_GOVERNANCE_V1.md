# AION BUSINESS Pilot Governance V1

Schema: `ATLASQUANT_AION_BUSINESS_PILOT_GOVERNANCE_V1`

## Objetivo

Definir, antes de qualquer cliente real, como deve funcionar o primeiro piloto
controlado do AION Business.

O módulo não libera piloto. Ele apenas cria charter, gates, critérios de sucesso,
condições de parada e packet para futura aprovação humana explícita.

## Limites do primeiro piloto

O desenho inicial é propositalmente estreito:

- 1 cliente;
- 1 workflow;
- no máximo 2 canais;
- no máximo 2 operadores humanos;
- duração máxima de 30 dias;
- suporte com responsável nomeado;
- runtime OFF nesta V1;
- mensagens externas OFF;
- publicação OFF;
- pagamentos OFF;
- ação externa diária = 0 nesta V1.

## Charter

O charter precisa nomear:

- cliente;
- segmento;
- pacote;
- workflow;
- canais;
- duração;
- operadores humanos;
- responsável de suporte.

Sem isso, o estado fica `INCOMPLETE`.

Se qualquer capacidade externa vier ligada nesta V1, o estado fica `BLOCKED`.

## Gates obrigatórios

Antes de sequer pedir aprovação de piloto:

- especialista BUSINESS certificado;
- DEMO completo no Painel Mestre;
- escopo revisado;
- privacidade revisada;
- SLA revisado;
- margem revisada;
- capacidade revisada;
- integrações revisadas;
- rollback revisado;
- operador humano definido;
- suporte definido;
- critérios de sucesso definidos;
- condições de parada definidas.

Gate ausente = piloto bloqueado.

## Critérios de sucesso

O piloto precisa definir:

- métricas;
- amostra mínima;
- cadência de revisão.

Resultado financeiro nunca é garantido.

## Condições de parada

Parar/escalar quando houver, no mínimo:

- risco de privacidade/permissão;
- incidente crítico;
- ação externa inesperada.

Também podem ser usados:

- padrão de quebra de SLA;
- estouro de margem/capacidade;
- falha de qualidade de dados;
- operador indisponível;
- pedido do cliente.

## Autoridade

Mesmo quando todos os gates passarem, o máximo permitido é:

`HUMAN_PILOT_APPROVAL_REQUIRED`

Isso ainda não significa:

- piloto autorizado;
- runtime aprovado;
- contato liberado;
- publicação liberada;
- pagamento liberado.

## Segurança

DEMO pronto ≠ PILOT autorizado.

PILOT elegível ≠ LIVE autorizado.
