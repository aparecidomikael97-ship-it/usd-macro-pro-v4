# AtlasQuant Trader — pacote canônico para pré-registro G8/28 D1+W1 (LAB)

Data da preparação: 06/11/2026. Sem sinais produzidos, compras, serviços pagos,
rede, agendamento, deploy ou alteração da interface. **É um formato de arquivo,
não um registro externo efetivado.**

## Comprovação remota do universo vazio

Consulta de leitura ao GitHub em 06/11/2026:

- O manifesto `TRADER_G8_20261108_D1W1_FROZEN_COHORT_LAB.json` consta na
  PR [#1815](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1815),
  em estado DRAFT, com 56 slots e **zero previsões**.
- A revisão remota consultada foi `410a055548a2a707a308671868c068500548b07b`.
  O objeto Git blob do manifesto retornou
  `14aea194bfdf83179a8605a1b13ccb10fd73ed0b`, idêntico ao resultado
  de `git hash-object` sobre os bytes locais.
- SHA-256 dos bytes do manifesto:
  `accada99955bd319d84ab528f5ace8f597fce29342f58fc079c09d37595e38ab`.
- A API GitHub informou PR criada em `2026-11-04T20:16:03Z` e atualizada em
  `2026-11-06T14:19:10Z`. **Isso prova somente que recebemos metadados e
  conteúdo desse estado remoto**, não que uma previsão direcional foi publicada
  num horário independente. GitHub permite mover branches e atualizar PRs;
  datas gravadas dentro de commits Git podem ser declaradas pelo autor.

## Problema resolvido no laboratório

Os validadores anteriores tinham um universo fixo de 56 vagas, um ledger de
claims com ALTA/BAIXA/NEUTRO/AGUARDAR e a checagem de bytes macro. Faltava
**um único objeto determinístico e imutável por conteúdo**, reunindo os 56
slots para futura publicação e testemunho por terceiro antes do movimento.

O módulo `atlasquant_trader_fx_g8_precommit_packet_lab.py` acrescenta:

- `prepare_g8_precommit_packet_lab(...)`: recebe manifesto canônico, ledger
  **completamente preenchido pelo pesquisador** e bytes macro de cada
  ALTA/BAIXA/NEUTRO. Reexecuta as verificações precedentes, exige 56/56
  registros válidos e ainda dentro do prazo, ordena pelo universo congelado
  e produz **bytes JSON canônicos + SHA-256**. Não atribui direção por conta
  própria. AGUARDAR é uma abstenção, nunca um acerto.
- `inspect_g8_precommit_packet_lab(...)`: refaz o pacote a partir dos mesmos
  insumos e exige **igualdade byte a byte**. Pode verificar integridade depois
  da sessão, mas não comprova que o pacote realmente existia no passado.

O pacote registra o identificador do estudo, hashes de manifesto, ledger e
evidências macro vinculadas, data de preparação **alegada** e todas as 56
entradas. Os campos de testemunha externa permanecem `null`, assim como
qualquer alegação de acurácia.

## Prazo de pesquisa e fuso

| Referência | UTC | Manaus/MT (UTC−4) | Brasília (UTC−3) |
|---|---|---|---|
| Limite de pré-registro | 08/11/2026 21h | Domingo 17h | Domingo 18h |
| Início D1 e W1 | 08/11/2026 22h | Domingo 18h | Domingo 19h |
| Fim D1 | 09/11/2026 22h | Segunda 18h | Segunda 19h |
| Fim W1 | 13/11/2026 22h | Sexta 18h | Sexta 19h |

O relógio do próprio computador **não constitui prova externa**. O horário
de Nova York (17h NY) define as janelas para a pesquisa, mas não certifica
o horário de negociação de nenhuma corretora.

## O que NÃO aconteceu

- Não publicamos um pacote com direções reais nem criamos previsões.
- Não carimbamos o horário de pacote de previsão num serviço externo.
- Não verificamos ainda a publicação histórica das fontes macro, a versão
  congelada e calibrada do modelo, os preços independentes ou a taxa de acerto.
- Não ativamos nenhuma coleta, resposta automatizada, Worker, Scheduler,
  Radar, execução, merge ou deploy.

`validated_prediction_count=0`, `validated_accuracy=null`, `fx_bias=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`, custo novo `R$0`.

Os 16 testes novos usam apenas declarações e evidências **sintéticas**;
verificam o pacote com 56/56 AGUARDAR, um claim misto, os 28 pares e ambos
horizontes, ausência/duplicação, macro adulterado, prazo vencido e tentativa de
injetar testemunha ou acurácia no JSON. **Nenhum teste representa um acerto
real de Forex.**

Próxima comprovação obrigatória: registrar externamente os bytes exatos de
um pacote real **antes do prazo**, obter um recibo de servidor independente
que identifique o conteúdo, recuperá-lo depois e verificar a integridade.
Somente então passar à avaliação futura D1/W1 com preços reais confiáveis,
considerando todas as 56 posições, inclusive abstenções e dados ausentes.
