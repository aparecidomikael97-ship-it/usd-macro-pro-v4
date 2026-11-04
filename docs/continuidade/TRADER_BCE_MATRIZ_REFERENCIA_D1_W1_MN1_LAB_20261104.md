# AtlasQuant Trader — matriz BCE D1/W1/MN1, só referência retrospectiva

**Checkpoint de 04/11/2026. Vinculação P1: força relativa das oito moedas
G8 e 28 pares com horizontes diário, semanal e mensal.**

## Objetivo

Tornar comparáveis, lado a lado, as variações históricas das taxas de
referência do BCE para **USD, EUR, GBP, JPY, CHF, AUD, CAD e NZD**.
Isso responde *como as referências variaram* — não *por que o preço se
moveu* nem *em que direção vai negociar no futuro*.

## Entrega em LAB

- `atlasquant_ecb_g8_reference_lab.py`: além de D1 e W1, calcula **MN1
  móvel de 30 dias corridos** usando somente uma observação real anterior
  ou igual à data de corte; jamais inventa taxa para fins de semana.
- `atlasquant_trader_ecb_three_horizon_matrix_lab.py`: **28 pares × 3
  horizontes = 84 quadros** com variação retrospectiva percentual,
  datas inicial/final, tempo real decorrido e ranking relativo de oito
  moedas por horizonte. Exibe as dez maiores altas de referência de cada
  horizonte quando há histórico suficiente.
- Caso não haja ancoragem de aproximadamente sete ou 30 dias, retorna
  `INSUFFICIENT_REFERENCE_HISTORY` para esse horizonte, em vez de usar
  qualquer observação muito antiga.
- Protege o rótulo diário contra comparações com intervalo maior que sete
  dias e indica explicitamente quando a referência está há mais de
  quatro dias sem nova data declarada.
- Para cada par e horizonte, o **viés operacional permanece `AGUARDAR`**;
  fundamento macro/micro, geopolítica, notícias, calendário, resposta
  real de mercado e contraprovas seguem pendentes de validação.

## Limites que não podem ser escondidos

1. Entrada: bytes XML **fornecidos pelo chamador**, sem prova de download
   ou origem autenticada nesta rotina.
2. Fonte: **sete taxas do euro**. Os 28 pares são calculados por álgebra;
   os 21 pares sem EUR não constituem cotações independentes.
3. Não há bid/ask negociável, spread, M15, feed de preço contínuo,
   calendário real, explicação causal ou acurácia preditiva comprovada.
4. Um ranking histórico não é sinal, probabilidade nem viés do futuro;
   D1/W1/MN1 aqui descrevem janelas retrospectivas, não previsão macro.
5. **Mês** significa janela móvel de **30 dias corridos**, não todo o
   calendário do mês atual. Isso será rotulado explicitamente na interface.

O BCE informa que suas taxas são **informativas**, normalmente divulgadas
nos dias úteis, e não recomenda seu emprego como preços de transação.
Referência: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

## Testes

Comando local:

```bash
python -m unittest discover -s . -p 'test_atlasquant_trader_*lab.py' -q
```

**11 testes locais novos aprovados**, verificando as três janelas,
inversão de direção entre dia/semana/mês, lacunas, taxas falsas e
proibições de uso operacional. O ambiente de trabalho combinado também
passou em **244 testes locais do Trader**; esse conjunto inclui módulos
da PR #1803 ainda não integrados à branch do BCE. **Não equivale a 244
testes remotos executados na PR #1811.** A validação de CI precisa ser
confirmada no SHA correspondente.

Nenhuma coleta automática, Worker, Render, assinatura comercial, ordem,
merge ou deploy foi executado. Esta melhoria pertence à **PR #1811 do BCE,
em DRAFT/LAB**; a PR #1803, também em DRAFT, segue separada com seu
conflito de integração pendente.

**Próxima etapa:** acoplar essa matriz retrospectiva às explicações
macroeconômicas e às contraprovas, com fontes reais e dados de preço
independentes, sem promover variações do BCE a sinais de compra/venda.
