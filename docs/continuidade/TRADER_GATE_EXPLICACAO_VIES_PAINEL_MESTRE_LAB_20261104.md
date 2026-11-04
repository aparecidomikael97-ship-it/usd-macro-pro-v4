# AtlasQuant Trader — gate de explicação do viés | LAB 04/11/2026

## Ligação com o Checkpoint Mestre

**P1:** macro, micro, geopolítica, notícias, calendário e força relativa das
oito moedas; demonstrar **por que** a moeda-base estaria forte ou fraca
contra a cotada em **D1/W1/MN1**, sem alegar uma causalidade não provada.

**P2:** três atualizações documentais planejadas por dia: **06:35, 10:45 e
17:15 BRT**. No presente LAB, a agenda é **somente planejada**. Não existe
prova de coleta automática, agenda ativada, fonte autenticada ou noticiário
em tempo real. Atualização horária paga permanece adiada.

## Implementação

- `atlasquant_trader_explanation_release_gate_lab.py` monta **28 cartões de
  pares**, cada um com explicação separada para D1/W1/MN1: **84 avaliações**.
- Recalcula a auditoria de cobertura documental para cada uma das **oito
  moedas × nove dimensões** e o dossiê macro de diferenças sintéticas
  entre consenso e valor divulgado. Não aceita os dados como fatos reais.
- Mostra precisamente quais dimensões faltam em cada lado do par, quais
  fontes têm última verificação declarada mais antiga que 48 horas e quantas
  notícias/divulgações **documentais ou sintéticas** foram fornecidas.
- Mostra os bloqueios: sem comprovante independente das três execuções,
  custódia dos dados, contraprovas independentes, resposta do mercado aos
  dados, validação de cotações independentes e prova de causalidade.
- Uma surpresa de CPI acima do consenso **não** equivale automaticamente a
  dólar forte; expectativas de juros, cenário anterior e resposta do câmbio
  precisam ser investigados antes de qualquer conclusão.
- Indica sempre `AGUARDAR`/`NAO_PUBLICAVEL_COMO_FATO`, inclusive quando
  todas as nove dimensões possuem links documentais declarados.
- Entradas malformadas, fabricadas, futuras ou previamente promovidas a
  `ALTA`/`BAIXA` são rejeitadas com `LAB_BLOCKED`.

## Cobertura verificada localmente

Comando executado em 04/11/2026:

```bash
python -m unittest discover -s . -p 'test_atlasquant_trader_*lab.py' -q
```

**195 testes locais aprovados (0 falhas/erros)**, dos quais **12 novos** para
o gate. O workflow de qualidade recebeu a referência explícita ao teste
do novo gate, preservando a lista maior já existente no GitHub. **A execução
de CI no GitHub neste SHA não está confirmada**; testes locais não são
prova de dados reais.

## Bloqueios mantidos

- Nenhum job de coleta 3×/dia, HTTP, Worker, Render ou deploy é ativado.
- Nenhuma contratação, fonte paga, ordem, recomendação financeira
  automática ou alteração da aplicação publicada.
- Não afirmar que há força relativa real ou viés diário/semanal/mensal
  verificado enquanto não existir prova externa autenticada.
- Permanecer na **PR #1803 em DRAFT/LAB**. A revisão exibe conflito com
  `main`; não tentar mesclar ou publicar sem revisão e autorização.

Próximo passo seguro: prover dados de fonte oficial com comprovantes
independentes de horário/alteração e revisão das evidências contrárias para
reduzir lacunas gradualmente, sem reclassificar links como fatos observados.
