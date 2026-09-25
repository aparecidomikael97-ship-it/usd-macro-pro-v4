# AION — Real-Time Event Intelligence + Impact Engine

Data de consolidação: 2026-09-25

## Objetivo

Permitir que o AION acompanhe eventos e notícias produzidos pelo runtime do
AtlasQuant, organize a evidência, estime mecanismos possíveis de impacto de
mercado e gere alertas internos auditáveis.

A camada não transforma manchete em verdade, cenário em sinal ou alerta em
ordem.

## Pipeline

Fluxo oficial:

1. Autopilot obtém/atualiza o snapshot de notícias pelo fluxo já existente.
2. Event Intelligence consome o mesmo snapshot, sem chamada extra de provedor.
3. Artigos são deduplicados por story/event fingerprint.
4. O AION separa:
   - relatório/manchete observada;
   - fato confirmado;
   - classificação inferida;
   - hipótese de impacto.
5. O evento recebe categoria e severidade.
6. O Impact Engine cria canais de impacto possíveis e invalidadores.
7. O Reliability Guardian governa o alerta.
8. O alerta fica interno e auditável.
9. Eventos/alertas podem ser sincronizados com o Checkpoint Mestre.
10. Nenhuma ordem ou notificação externa é executada automaticamente.

## Estados de verdade

### Report truth

CONFIRMED significa apenas que o AtlasQuant observou aquele item no feed
persistido com proveniência confirmada.

Isso NÃO prova que o conteúdo factual da manchete é verdadeiro.

### Event truth

- CONFIRMED: fonte oficial/estruturada adequada para a afirmação.
- INFERENCE: evidência convergente, mas ainda não promovida a fato oficial.
- UNKNOWN: fato não confirmado.

### Classification truth

A classificação temática/direcional por palavras e regras é sempre INFERENCE.

### Impact truth

Todo impacto por ativo é HYPOTHESIS.

Exemplos:
- petróleo pode receber prêmio de risco;
- ouro pode receber demanda defensiva;
- JPY/CHF podem receber fluxo defensivo;
- índices podem sofrer risk-off;
- WDO pode receber pressão de alta em busca por dólar.

Esses mecanismos podem falhar ou ser invertidos. O painel mostra invalidadores.

## Categorias iniciais

- GEOPOLITICAL_ESCALATION
- GEOPOLITICAL_DEESCALATION
- CENTRAL_BANK_HAWKISH
- CENTRAL_BANK_DOVISH
- INFLATION
- LABOR
- GROWTH
- ENERGY_SUPPLY
- TRADE_FISCAL_POLICY
- SYSTEMIC_RISK
- GENERAL_MARKET

## Alertas

Estados:

- NONE
- WATCH
- REVIEW_INTERNAL
- URGENT_INTERNAL
- HOLD

URGENT_INTERNAL é revisão imediata dentro do AION, não ordem nem push externo.

Reliability FAIL_CLOSED transforma alertas dependentes em HOLD.

## Background 24/7

O Autopilot passa a persistir:

`dados/aion_event_intelligence_v1.json`

A geração de Event Intelligence:
- reutiliza o snapshot de notícias já obtido;
- não adiciona chamada ao NewsAPI/Twelve/EODHD;
- não envia mensagem;
- não publica;
- não compra serviço;
- não executa trade.

O ciclo real depende do runner/runtime estar efetivamente ativo. Código
disponível no GitHub não prova que o serviço de produção está executando esse
ciclo.

## Checkpoint Mestre

Namespace:

`event_intelligence`

Contém:
- `events`: diário compacto deduplicado;
- `alerts`: alertas internos deduplicados;
- `digest`: proteção de integridade.

A interface permite sincronizar o diário runtime para a memória de trabalho do
Checkpoint. Persistência definitiva continua usando o fluxo explícito de salvar
o Checkpoint Mestre.

## Interface

### Central AION

Exibe:
- eventos atuais;
- alertas ativos;
- urgentes internos;
- memória registrada;
- proveniência de background;
- fonte;
- idade;
- verdade do evento;
- categoria;
- hipóteses por ativo;
- invalidadores.

### Trading

Mostra Event Intelligence em modo somente leitura antes do Simulador de
Cenários Macro.

### Pulso Executivo

- URGENT_INTERNAL -> P1 Trading;
- REVIEW_INTERNAL/HOLD -> P2;
- WATCH -> P3.

P0 de integridade/reliability continua tendo precedência.

## Inteligência local e externa

Resposta local e prompt para modelo externo recebem:
- estado do alerta;
- evento principal;
- verdade do evento.

O prompt instrui explicitamente:
- reportagem observada != fato confirmado;
- classificação != fato;
- impacto != previsão;
- impacto != sinal;
- impacto != probabilidade de lucro.

## Travas permanentes desta camada

- Push externo automático: DESLIGADO.
- Canal WhatsApp/Telegram/e-mail/push: NÃO CONECTADO por esta camada.
- Chamada extra de provedor no Event Intelligence: NÃO.
- Mudança de score de trading: NÃO.
- Mudança automática de pesos/regras: NÃO.
- Autorização de ação de mercado: NÃO.
- Ordens reais: BLOQUEADAS.
