# AION — Índice de Independência CLT V1

## Objetivo

Acompanhar maturidade financeira do ecossistema para uma futura revisão da
transição do emprego para dedicação própria, sem transformar o índice em
recomendação.

## Entradas privadas

- faixa de renda líquida-base;
- histórico mensal de renda líquida não-Trade do ecossistema;
- multiplicador de segurança;
- meses mínimos de consistência;
- reserva em meses;
- participação de receita recorrente;
- concentração do maior cliente;
- dependência do Trade para despesas essenciais.

Nenhum desses valores precisa ser commitado no repositório.

## Zonas

### BUILDING
O ecossistema ainda está formando estabilidade.

### APPROACHING
Parte dos critérios já está atendida, mas ainda faltam gates relevantes.

### TRANSITION_REVIEW_ZONE
Os gates críticos estão atendidos e existe evidência suficiente para uma revisão
humana mais profunda.

Isso não significa "sair do emprego".

## Gates críticos

- renda não-Trade atinge a faixa de segurança;
- consistência por meses suficientes;
- reserva atinge o mínimo definido;
- receita recorrente atende ao piso;
- concentração do maior cliente não excede o teto;
- despesas essenciais não dependem do Trade.

## Regra de decisão

`employment_exit_recommended=false` sempre.

O AION apenas organiza evidência e perguntas. A decisão é do usuário.
