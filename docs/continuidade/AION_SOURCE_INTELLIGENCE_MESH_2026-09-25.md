# AION — Source Intelligence Mesh

Data de consolidação: 2026-09-25

## Objetivo

Transformar os estados e dados que o AtlasQuant já calcula em uma malha
auditável de fontes para o Reliability Guardian.

O Source Mesh não faz chamadas externas próprias. Ele recebe evidências do
runtime existente e as classifica.

## Fontes conectadas nesta fundação

### FRED / macro dos EUA
Usa a auditoria já gerada por `carregar_macro_eua()`.

Cada indicador recebe:
- fonte;
- valor;
- idade;
- limite de frescor;
- criticidade;
- verdade CONFIRMED somente quando a origem é FRED.

Valor de segurança/fallback permanece UNKNOWN/indisponível como fonte atual.

### Calendário macro
Usa o próximo evento já resolvido pelo motor de calendário.

CONFIRMED exige proveniência explícita do evento. Evento sem fonte registrada
não é promovido a confirmado.

### Autopilot Runtime
Lê o status persistido já usado pelo projeto:
`dados/autopilot_status_v107.json`.

São observados:
- ciclo do Autopilot;
- saúde do app headless;
- idade do último ciclo;
- mercado aberto/fechado;
- scanner técnico;
- market map;
- Twelve Data;
- orçamento/quota Twelve quando presente;
- notícias persistidas;
- News Nowcast/EODHD quando presente no status.

### Currency News Runtime
Pode ler:
`dados/currency_news_current_v107.json`.

Frescor é medido pela data `updated_at`; conteúdo antigo não é tratado como
notícia atual.

### Pair Matrix
Usa `atlasquant_pair_matrix_status`.

Estados relevantes:
- live + pronta;
- indisponível;
- runtime snapshot.

Runtime snapshot pode manter continuidade de interface, mas não confirma
mercado ao vivo.

### Narrativa Fed por RSS
A leitura heurística atual do Fed é incluída como INFERENCE quando existem
manchetes analisadas.

Isso não é tratado como comunicado oficial nem fato confirmado do Fed.

## Regra de mercado ao vivo

`market_live_confirmed=True` somente quando:

1. mercado está aberto;
2. Autopilot tem proveniência confirmada e está saudável;
3. Twelve Data está confirmado e saudável;
4. scanner técnico está confirmado e saudável;
5. market map está confirmado e saudável;
6. Pair Matrix está pronta e `live_ready=True`.

Se uma peça falhar, faltar ou vier de snapshot, o estado não vira
LIVE_CONFIRMED.

## Relação com Reliability Guardian

As observações do Source Mesh entram em `system_context.source_observations`.

O Reliability Guardian então aplica:
- stale;
- degraded;
- unavailable;
- unknown;
- conflict;
- criticidade;
- fail-closed quando aplicável.

O Source Mesh não resolve conflitos sozinho e não troca de fonte
automaticamente.

## Segurança

- chamadas de rede próprias do Source Mesh: NÃO;
- alteração de scores: NÃO;
- troca automática de fonte: NÃO;
- fallback pago automático: NÃO;
- autorização de trade: NÃO;
- ordens reais: BLOQUEADAS.

## Verdade operacional

Fonte configurada ≠ fonte saudável.

Credencial presente ≠ dado atual.

Fallback ≠ observação ao vivo.

Snapshot ≠ live.

Notícia/RSS analisada ≠ comunicado oficial.

O AION deve manter essas diferenças visíveis ao administrador.
