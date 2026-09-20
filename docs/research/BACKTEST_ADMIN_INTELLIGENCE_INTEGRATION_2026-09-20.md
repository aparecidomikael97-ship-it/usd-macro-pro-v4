# AtlasQuant — Backtest + Admin Intelligence Integration · 20/09/2026

Este bloco liga a fundação de pesquisa operacional ao uso prático do Backtest e
do Administrador.

## Diagnóstico de gain/loss

Todo trade executado passa a receber duas leituras separadas:

1. **mecânica do resultado** — alvo, stop, saída por tempo ou ambiguidade OHLC;
2. **qualidade/contexto da decisão** — somente quando existe snapshot histórico
   point-in-time suficiente.

O sistema não deduz que "stop = análise errada" nem que "alvo = análise boa".
Um gain pode ser classificado como decisão fraca e um loss pode ocorrer apesar
de uma decisão coerente.

As causas contextuais são chamadas de fatores/evidências prováveis; causalidade
não é declarada sem evidência apropriada.

## Contexto histórico point-in-time

A aba Backtest aceita um terceiro CSV opcional de snapshots históricos.

Campos centrais:
- captured_at;
- pair;
- macro_alignment;
- technical_confirmation;
- liquidity_confirmation;
- regime_fit / regime;
- known_high_impact_event;
- data_quality_pct;
- plan_followed;
- event_time / event_label / event_impact.

Para cada sinal, somente o snapshot mais recente cuja captura seja anterior ou
igual ao signal_time pode ser usado.

Metadado explícito no próprio sinal tem precedência e nunca é sobrescrito pelo
join. Snapshot futuro é rejeitado por design.

Sem contexto histórico suficiente, o AtlasQuant mostra a explicação mecânica e
lista o que está faltando. Ele não fabrica notícia, macro ou regime depois de
ver o resultado.

## Padrões recorrentes de gain/loss

O Backtest agrega os códigos/fatores associados a Gains, Losses e Breakevens.
A tabela mostra frequência dentro de cada resultado, mas permanece
descritiva — associação não é prova de causalidade.

## Passaporte do Operacional

Cada backtest individual produz Passaporte com:
- amostra;
- expectativa observada;
- profit factor;
- net R;
- drawdown;
- ativos/sessões/regimes cobertos;
- qualidade de dados quando disponível;
- lacunas de validação;
- paper ainda pendente quando não existe.

O Comparador dos cinco operacionais também cria um Passaporte separado para:
- BOS/CHOCH + Order Block;
- FVG;
- OTE;
- CRT;
- AMD / Power of Three.

Esses Passaportes são enviados para o estado da sessão do Admin. Não existe
promoção automática.

## Admin · Inteligência dos Operacionais

A área Melhorias passa a incluir um painel de pesquisa reservado a ADMIN
(ou ambiente OPEN de desenvolvimento privado), com:
- Matriz Mestre ICT/SMC/Price Action;
- último Passaporte;
- Passaportes do Comparador;
- diagnóstico individual;
- fatores recorrentes de gain/loss;
- Perfil Semanal estatístico;
- Detector de Mudança de Comportamento.

Usuário USER/PREVIEW não recebe controles administrativos.

## Perfil Semanal

O Admin pode importar OHLC diário e medir em qual dia highs/lows semanais
realmente ocorreram. Terça/quarta é uma hipótese medida, nunca uma regra fixa.

## Detector de Mudança de Comportamento

O Admin pode comparar baseline × período recente de:
- expansão Londres;
- expansão Nova York;
- follow-through após sweep;
- reversão após sweep;
- reação em níveis;
- range médio.

O detector sinaliza mudança observável, mas não afirma conhecer intenção oculta
de instituições e não muda estratégia automaticamente.

## Segurança preservada

- Real orders: OFF.
- Auto-promoção: OFF.
- Auto-alteração de estratégia: OFF.
- Look-ahead em diagnóstico: proibido.
- Contexto ausente: UNKNOWN, não inventado.
- Ranking histórico: descrição de amostra, não promessa de resultado.

Próxima evolução: persistir esses relatórios entre sessões e cruzar
Backtest × Walk-forward × Shadow × Paper no Passaporte do Operacional.
