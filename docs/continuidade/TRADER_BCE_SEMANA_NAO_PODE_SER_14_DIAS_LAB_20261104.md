# AtlasQuant Trader — evitar falsa janela semanal na referência BCE

Checkpoint LAB de 04/11/2026. A prioridade segue sendo a força relativa das
oito moedas G8 e a explicação dos 28 pares em **D1/W1/MN1**. Isso é apenas
comparação retrospectiva do BCE, não previsão de direção do mercado.

## Problema observado

O adaptador do BCE seleciona a última taxa efetivamente publicada **na data
anterior ou igual** ao corte de sete ou 30 dias. Antes, a tolerância de
até sete dias extras também valia para W1. Assim, uma taxa de **14 dias**
atrás poderia entrar numa linha intitulada "semanal".

## Ajuste aplicado

- **W1:** a data de referência inicial precisa estar entre **7 e 11 dias**
  antes da última, contando dias corridos. Aceitamos até quatro dias
  adicionais para acomodar fechamentos sem interpolar taxas.
- **MN1:** segue janela móvel de **30 a 37 dias**, com no máximo sete dias
  de folga documental, sempre mostrando as datas efetivas.
- Se o registro anterior estiver além do limite, a janela recebe
  `INSUFFICIENT_REFERENCE_HISTORY`, com ranking vazio e viés
  operacional `AGUARDAR`, mesmo que D1 e MN1 tenham histórico.
- Para janela utilizável, o resultado carrega período-alvo, dias de
  tolerância usados e intervalo real entre datas. Isso permite conferir
  se a comparação foi de sete, oito ou onze dias.

Esses limites são **decisões conservadoras de pesquisa**, não exigências
publicadas pelo BCE. Feriados não autorizam inventar cotações ausentes.

## Verificações

- Histórico com próxima referência anterior apenas **14 dias antes**:
  W1 indisponível, mesmo com MN1 utilizável.
- Janela legítima de **oito dias**: identificada como oito dias, com
  tolerância efetiva de um dia.

Depois da alteração, **271 testes locais do Trader passaram** no
workspace combinado (dois novos). Esse número abrange módulos da PR
#1803 que não fazem parte da PR BCE #1811 e não substitui CI remoto.

Continuam pendentes o motivo macroeconômico comprovado, a geopolítica,
notícias e calendário autenticados, preço FX independente, validação
fora da amostra e a execução real das três atualizações diárias.
Nenhum deploy, merge, Render, Worker, custo ou ordem foi ativado.
