# AtlasQuant Trader — proteção anti-futuro das referências BCE (LAB)

Checkpoint de 04/11/2026. O foco segue no viés D1/W1/MN1 de 28 pares,
força de oito moedas e causas macro/micro/geopolíticas com notícias e
calendário verificáveis. Esta etapa corrige um risco da **matriz histórica**.

## Problema

O XML do BCE identifica o fixing com a data, não com um timestamp de
divulgação individual comprovado. Antes, uma taxa de `2026-11-04` poderia
ser aceita como "de hoje" até às 06h, apesar de a publicação oficial
habitual ocorrer por volta das **16h no horário europeu**, em dias úteis
(exceto fechamentos TARGET). Isso seria olhar para uma referência que ainda
não estaria disponível naquela manhã.

Fonte oficial do horário e da natureza informativa das taxas:
https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

## Alterações isoladas na PR #1811

- Usa o **dia civil da Europa/Bruxelas**, considerando horário de verão,
  ao comparar a data do XML com a data de avaliação.
- Recusa fixing com data **igual ao dia europeu atual antes de 16h locais**.
  Atingir esse horário é somente um limite inferior, **não autentica que
  uma publicação efetivamente ocorreu**; a fonte continua não atestada.
- Recusa qualquer observação histórica com data de **sábado ou domingo**, não
  apenas a mais recente, e datas futuras em relação
  ao calendário europeu. Não tenta determinar feriados TARGET sem a
  respectiva prova oficial.
- Calcula a idade da referência segundo a data europeia, e mantém
  `AGUARDAR` para todo viés operacional.
- Na ponte de notícias com macro, converte o carimbo do evento para
  **Europa/Bruxelas antes de comparar com datas BCE**. Exemplo: evento
  `2026-11-03 23:30 UTC` já é `2026-11-04 00:30 CET`, portanto está
  **depois** do fixing etiquetado `2026-11-03`, não "no mesmo dia".

## Testes executados

- Inverno: mesmo dia às 15:59 CET recusa; 16:01 CET permite apenas
  **pesquisa retrospectiva não autenticada**.
- Verão: comparação equivalente respeita CEST e horário UTC distinto.
- Data de sábado: recusa a taxa fabricada, inclusive quando ela é um
  **ponto histórico anterior** que poderia contaminar o mês.
- Notícias às 23:30 UTC: classificadas com a data europeia correta.

No scratch combinado, **269 testes locais Trader passaram** após o ajuste,
incluindo os 5 novos testes. Esse total abrange a PR #1803, ainda separada;
não constitui resultado do CI remoto da PR #1811.

Sem API contratada, cron, Worker, Render, merge, deploy ou operação real.
O viés D1/W1/MN1 continua `AGUARDAR` até fatos macroeconômicos e preços
independentes poderem ser verificados, com contraprovas e teste OOS.
