# AION FinOps — Reservas Atômicas SQLite Efêmeras V1

**Data:** 2026-10-08  
**Escopo:** PR Draft, testes Windows/Linux em runner GitHub, sem efeitos financeiros reais  
**Base:** PR #1070 — teto pessoal planejado R$ 200/mês em BRL

## Por que isto é necessário

O contrato de orçamento da #1070 rejeita uma nova prévia acima do teto.
Mas, se duas solicitações verificarem simultaneamente os mesmos R$ 80
disponíveis, cada uma pode parecer permitida isoladamente. Precisamos
de **admissão e reserva atômica** para evitar essa corrida antes de
integrar o sistema a qualquer provedor pago.

Esta V1 demonstra um algoritmo transacional **exclusivamente em SQLite
temporário do runner de pull_request do GitHub**. Ela NÃO opera o AION
em produção, não intercepta APIs pagas e não altera dados do computador
do proprietário.

## Algoritmo e segurança

- Recebe um orçamento prévio da #1070 com todos os campos esperados,
  digest rechecado e todos os flags de autoridade real = falso.
- Inicializa um mês por proprietário e fixa (congela) sua linha de base,
  recusando reduções silenciosas durante o mês.
- Apenas na CI explicitamente habilitada, cria um SQLite temporário
  dentro de `RUNNER_TEMP`; o caminho deve estar contido na pasta
  temporária, com prefixo restrito e sem symlinks no destino.
- Em cada reserva aplica `BEGIN IMMEDIATE`, lê o contador e confere
  com `SUM(amount_cents)` das reservas realmente registradas,
  verifica `base + reservado + novo <= 20.000 centavos` e registra
  a solicitação na mesma transação.
- Cada tentativa tem ID único; a mesma solicitação repetida retorna
  o mesmo estado sem duplicar consumo. Mesmo ID com outro custo,
  cliente, prestador ou escopo é bloqueado.
- A cotação em dólar é obtida como entrada datada da #1070, com buffer
  conservador de 10%, e um custo ausente/inválido não obtém reserva.
- Não há liberação automática de valor. Um `SETTLED` estimado é
  registrado sem reduzir o valor reservado; tentativa de liquidação
  acima do reservado ou diferente de anterior é recusada.
- O relatório mensal reabre o banco por conexão independente e confere
  novamente os contadores; qualquer divergência de contabilidade
  bloqueia novas propostas.

### Resultado dos casos de teste

Dois pedidos de R$ 50, com base R$ 120 e teto R$ 200,
concorrem pela disponibilidade de R$ 80:
**exatamente um pedido de R$ 50** deve receber a reserva efêmera
(o outro falha). Nenhum recebe aprovação para cobrança ou autorização
de execução real. Uma segunda bateria usa cinco pedidos simultâneos.

## O que a reserva NÃO significa

**Reserva em SQLite não significa dinheiro reservado no cartão/banco ou
crédito garantido em um provedor.** Também não comprova que a fatura
será menor que R$ 200. Os componentes da #1070 e desta PR aceitam
inputs de custos declarados, não notas fiscais autenticadas.

O SQLite escreve páginas e arquivos temporários reais **no disco do
runner de CI do GitHub**. Esse runner não é o computador do usuário.
O diretório de teste é descartado após os testes. Os guards de
variáveis de ambiente podem ser falsificados e não são uma barreira
autoritativa contra uso deliberado fora de CI; o módulo não pode ser
usado como controle financeiro de produção.

A execução de chamadas pagas, cobranças e fallback pago continuam
sempre desautorizados nos retornos. Não há importação de chave
financeira, PIX, cartão, webhook, API de pagamento ou credencial.

## Faltas obrigatórias antes de aplicar na vida real

1. Levantar **todas** as faturas e compromissos do proprietário:
   mensal, anual pro rata, renovação, tributos, hospedagem e uso de APIs;
   validar quais custos podem crescer e quais são contratualmente fixos.
2. Validar RAM, VRAM e desempenho do computador para modelos locais;
   fallback local só deve ser anunciado se houver capacidade real.
3. Construir fonte confiável de custos/faturas, identidade do provedor,
   orçamento e reajustes, com confirmação independente dos saldos.
4. Integrar reserva transacional **antes** do endpoint que efetua a
   chamada paga, e garantir compensação e idempotência também no
   provedor externo; testar timeouts, faturamento tardio, retries,
   duplicação e concorrência entre instâncias.
5. Definir autenticação forte do proprietário, aprovação explícita
   com escopo, valor máximo, validade e uso único. A aprovação não
   é simulada nem consumida nesta PR.
6. Definir reembolso/liberação exclusivamente após prova
   independente de não cobrança, conciliação ou processo auditado;
   sem permitir dupla utilização.
7. Relatórios por prestador e cliente; a expansão B2B só deve
   ocorrer após comprovar margem real com impostos e suporte.

## Status máximo

`READY_FOR_FINOPS_TRANSACTIONAL_RESERVATION_SECURITY_REVIEW` —
somente evidência de correção do algoritmo em ambiente de teste.

**Sem merge, sem deploy, sem Worker, sem alteração de produção, sem
contratação, sem gasto novo, sem execução no computador do proprietário.**
