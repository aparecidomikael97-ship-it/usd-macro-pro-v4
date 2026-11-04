# AtlasQuant Trader — Revisões 3×/dia do calendário | LAB 04/11/2026

## Prioridade do proprietário

Este bloco atende às prioridades **P1 (notícias e calendário econômico) e
P2 (três verificações por dia)** do Checkpoint Mestre. A consequência para o
Trader é identificar **quais pares precisam de revisão humana quando um
evento econômico é incluído, remarcado, revisado ou explicitamente cancelado**.
Isso não determina se uma moeda ficará mais forte ou mais fraca.

## O que foi preparado

- `atlasquant_trader_calendar_three_daily_review_lab.py` recebe no máximo
  três envelopes **fornecidos externamente**, para as janelas planejadas
  **06h35, 10h45 e 17h15 de Brasília**. Não inicia a coleta.
- Compara versões sucessivas da **mesma origem declarada** por identificador
  e moeda, mesmo quando uma coleta intermediária estiver ausente.
- Mostra alteração de **data, situação, resumo documental (SHA-256
  declarado), carimbo do editor e novos eventos**, com prioridade de revisão.
- Lista os **28 pares Forex** e a contagem de ocorrências documentais de
  cada par. Os três vieses D1/W1/MN1 permanecem `AGUARDAR`.
- Identifica slots não apresentados, moedas sem documentos naquela captura,
  e verificações de fontes declaradas mais antigas que 48 horas.
- Um evento omitido de uma resposta **parcial** não vira automaticamente
  evento cancelado; uma nova informação só vai para a fila **humana**.
- Rejeita estrutura falsa, data futura, eventos duplicados, URLs que imitam
  domínios oficiais, mudança de moeda para a mesma origem e relógios
  incompatíveis.

## Limites expressos

Os documentos, horários, URLs e hashes são **alegações do fornecedor do
envelope**, não comprovantes de uma conexão real com banco central ou órgão
estatístico. Portanto:

- `source_authenticity_attested = false`.
- `three_daily_updates_verified = false`.
- `realtime_calendar_verified = false`.
- `notifications_sent = false`, sem alertas enviados.
- Nenhum processamento contínuo, Worker, Render, cobrança, ordem real ou
  publicação está autorizado. A PR #1803 segue DRAFT e em conflito com main.

## Verificação local

```bash
python -m unittest discover -s . -p 'test_atlasquant_trader_*lab.py' -q
```

**208 testes locais aprovados**, sem falhas/erros, incluindo **13 testes
novos** para o agregador de mudanças. A execução remota de CI ainda precisa
ser comprovada no commit correspondente.

## Próximo bloco seguro

Receber e preservar bytes originais verificáveis de fontes oficiais, com
registro independente de identidade/origem/horário, dentro dos termos de uso
e sem custo novo. Somente depois distinguir alteração documental de
mudança real publicada. A avaliação de força relativa D1/W1/MN1 exige ainda
dados de câmbio independentes e validação fora da amostra.
