# AION FinOps — Budget Governor & Treasury V1

## Objetivo

Fazer o AION controlar custo e separar a função financeira de Negócios,
Trader e Investimentos.

## Orçamento mensal

Teto inicial: **R$200/mês**.

Faixas:
- abaixo de 70%: dentro da política;
- 70% a 84,99%: alerta;
- 85% a 100%: revisão crítica;
- acima de 100%: bloqueado.

O módulo não aumenta o teto sozinho.

## Tesouraria

### Negócios
É a principal fonte de financiamento do ecossistema na fase inicial.
Pode financiar operação do AION, reserva, crescimento, Investimentos e futuras
alocações limitadas ao Trader.

### Trader
Lucro líquido fica no próprio bucket Trader para reserva e crescimento gradual.
A política inicial limita a alocação do capital total do ecossistema ao Trader
a 30%. Esse limite é uma regra administrativa inicial, não uma afirmação de que
30% seja uma alocação universalmente ideal.

### Investimentos
Função principal: construção e preservação patrimonial.

## Metas de Trade

O AION pode calcular o percentual implícito de uma meta, mas:
- não classifica a meta como garantida;
- não a trata como retorno esperado;
- exige backtest, controles de risco e histórico real antes de depender dessa
  renda para despesas essenciais.

## Execução

Nenhuma função:
- gasta dinheiro;
- transfere capital;
- muda billing;
- aumenta orçamento;
- faz trade;
- admite cliente;
- chama provider externo.
