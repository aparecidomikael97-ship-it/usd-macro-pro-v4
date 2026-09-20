# AtlasQuant — Fundação Admin + Gestor de Posição por Evento

Atualizado em 20/09/2026.

## Objetivo

Transformar duas decisões de produto em contratos de código isolados antes de integrá-los à interface:

1. acompanhar posições abertas em torno de eventos macroeconômicos;
2. entregar ao Administrador um resumo de validação que não confunda lucro recente com robustez.

Nenhum item deste bloco envia ordens reais.

## Gestor de Posição por Evento

O módulo recebe:
- posição;
- moeda-base e moeda-cotada;
- lado LONG/SHORT;
- horizonte;
- evento;
- impacto;
- distância temporal;
- efeito esperado/classificado pelo motor macro upstream;
- estado de precificação quando disponível.

Ele devolve:
- se o evento afeta a posição;
- exposição da posição à moeda do evento;
- cenário alinhado, conflitante, neutro ou incerto;
- risco de janela próxima;
- flags de revisão;
- necessidade de revisão humana.

A classificação direcional do indicador continua sendo responsabilidade do motor macro. Este módulo não inventa direção e não transforma surpresa em ordem.

## Pós-evento

Depois da divulgação, o motor macro pode classificar o efeito realizado sobre a moeda. O Gestor reavalia se o novo contexto:
- está alinhado com a posição;
- conflita;
- é neutro;
- precisa de nova avaliação.

Mesmo quando alinhado, a saída continua sendo contexto, não "segure", "compre mais" ou "saia".

## Copiloto/Insights do Administrador

A fundação de Admin recebe métricas já calculadas por backtest/paper e separa:

- liderança observada da amostra;
- drawdown que merece atenção;
- amostra insuficiente;
- cobertura de regimes;
- profit factor;
- expectativa em R;
- divergência paper × backtest;
- qualidade dos dados;
- elegibilidade apenas para revisão humana.

Um setup com lucro alto e pouca amostra pode aparecer como líder observado e, ao mesmo tempo, ser bloqueado para avaliação do modo Iniciante.

## Regra de promoção

Nunca existe promoção automática para o modo Iniciante.

Fluxo:
**evidência estatística → consistência entre regimes → paper/backtest → qualidade dos dados → revisão humana → decisão de produto**.

A frase "foi o que mais lucrou esta semana" nunca é suficiente por si só.
