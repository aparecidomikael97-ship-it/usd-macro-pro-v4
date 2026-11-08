# AtlasQuant Trader — protocolo de âncora externa para previsão pré-notícia (LAB)

**Data:** 08/11/2026 · **Status:** código de laboratório, sem publicação de
previsão, agendamento, consulta HTTP, cobrança ou autorização de viés.

## Por que existe

O módulo `atlasquant_trader_event_forecast_lock_lab.py` gera uma previsão
identificada por SHA-256. Contudo, **é possível recalcular outro hash depois de
ver um resultado**. Precisamos de registro externo, feito antes da divulgação,
para sustentar a alegação de que a previsão realmente existia antes do evento.

## Novo módulo

- `atlasquant_trader_forecast_anchor_lab.py`
- `test_atlasquant_trader_forecast_anchor_lab.py`

`prepare_pre_event_anchor_lab` prepara apenas um pequeno texto que aponta para
o hash do registro de previsão, acompanhado do identificador do evento, do
horário de divulgação e de aviso de **uso exclusivamente experimental**.
O texto **não contém** valor anterior, consenso ou estimativa do modelo.
A preparação é recusada após chegar o horário programado do evento. Ela não
posta nem envia esse texto ao GitHub.

`assess_claimed_github_anchor_lab` compara o registro com um **objeto declarado**
como comentário do GitHub. Exige URL da API de comentários, número de comentário,
URL da PR/issue, corpo de texto exato, `created_at`, `updated_at`, `fetched_at`
e a identidade da PR/issue de destino. Verifica:

1. O comentário alegadamente criado **depois do registro da previsão e antes
   da divulgação**.
2. Nenhuma alegação de edição do comentário em horário posterior à divulgação.
3. Horário da consulta posterior ao último horário de edição e não posterior
   ao instante de avaliação.
4. Referências de GitHub e corpo do texto correspondentes ao hash original,
   sem anexos ou campos extras.

Um objeto com campos coerentes recebe o estado
`LAB_COMMENT_ANCHOR_CHRONOLOGY_CANDIDATE_UNATTESTED`, não uma aprovação.

## O que **ainda não** pode ser afirmado

- O módulo não consulta o GitHub. Quem chama a função pode inventar um objeto
  com `created_at` anterior; a validação do objeto **não autentica** a fonte.
- Falta implementar e testar consulta ao comentário através da API autenticada,
  vinculada ao repositório e evento corretos, para conferir os metadados
  emitidos pelo serviço. A forma como o serviço garante seus timestamps também
  deve ser auditada; uma data de commit fornecida pelo autor não basta.
- Ainda falta preservar a previsão completa, método e parâmetros fora da
  possibilidade de alteração sem trilha.
- A validade de consenso, dados anteriores e valor real do emissor oficial
  continua **não atestada**; a âncora só ajudaria a verificar um compromisso
  com um hash, e não se a previsão é boa.
- O exemplo CPI outubro/2026 nos testes contém **números artificiais**, não
  constitui previsão para 10/11/2026 e **não foi publicado**.

## Próximo passo controlado

Quando houver um registro **real e verificável** do modelo e das fontes
pré-evento, solicitar e guardar uma âncora externa com timestamp do servidor,
ler o registro por canal independente e confrontar com o hash. Depois do evento,
consultar o resultado oficial com prova de origem e avaliar erros em sequência
fora da amostra. Isso exige separação explícita entre pesquisa e produção.

Em todos os casos: `AGUARDAR`, sem score de probabilidade calibrada, sem
assertividade validada, sem vieses publicáveis, sem negociação, Worker, deploy,
HTTP ou custo. Prioridade continua AtlasQuant Trader — 28 FX e índices;
AION/Negócios congelados e PR de laboratório sem merge.
