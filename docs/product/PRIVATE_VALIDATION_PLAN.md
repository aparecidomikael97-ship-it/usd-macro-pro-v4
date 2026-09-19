# AtlasQuant — Plano de Validação Privada

## Objetivo

Manter o AtlasQuant privado durante a fase de observação para descobrir quais leituras e setups são realmente consistentes antes de qualquer decisão comercial.

## Janela inicial

Referência: **30–60 dias**, sem transformar tempo de calendário em aprovação automática. Se a amostra for pequena ou concentrada em um único regime, a validação continua.

## O que registrar por setup

- identificador e versão do setup;
- ativo/par;
- data/hora;
- sessão;
- regime de mercado;
- direção;
- contexto macro/fundamental;
- qualidade/frescor dos dados;
- hard/soft blocks;
- entrada teórica/paper;
- stop e alvo definidos antes do resultado;
- resultado em R;
- MAE/MFE quando disponível;
- spread/slippage/fricção usada;
- motivo de invalidação;
- screenshot/evidência quando disponível.

## Métricas mínimas de comparação

Não usar apenas win rate.

Comparar:
- quantidade de amostras;
- expectativa por trade;
- payoff médio;
- profit factor;
- drawdown;
- sequência máxima de perdas;
- estabilidade por semana;
- estabilidade por sessão;
- estabilidade por par;
- estabilidade por regime;
- diferença entre backtest e forward/paper;
- sensibilidade a custos/fricção;
- robustez de parâmetros.

## Seleção para o modo Iniciante

Um setup candidato só pode ser considerado para o modo Iniciante quando tiver:
- regra objetiva e ensinável;
- amostra suficiente;
- comportamento estável em mais de uma janela/regime;
- risco/drawdown compatível com o produto;
- forward/paper que não contradiga materialmente o backtest;
- explicação simples do que confirma, bloqueia e invalida.

A seleção continua **manual**. O sistema pode ranquear evidências, mas não promove setup automaticamente.

## Estados permitidos

- PESQUISA;
- BACKTEST;
- FORWARD/PAPER;
- CANDIDATO;
- APROVADO PARA REVISÃO;
- REJEITADO/REVER.

Não existe estado automático “PRONTO PARA VENDER”.

## Segurança

Durante esta fase:
- broker real permanece desligado;
- ordens reais permanecem desligadas;
- alterações automáticas de gate/pesos permanecem desligadas;
- resultados passados não são tratados como promessa futura.

## Implementação no AtlasQuant

A infraestrutura desta fase fica separada do motor operacional:

- `atlasquant_setup_validation.py`: catálogo e critérios mínimos para **revisão humana**;
- `atlasquant_setup_journal.py`: esquema de planilha/observações Forward/Paper por setup;
- `autopilot_setup_audit_v114.py`: congela prospectivamente o contexto do Paper Trading, incluindo componentes ICT/SMC e, quando disponível, regime D1/W1, sessão, Premium/Discount e sweep;
- a aba **Melhorias** no modo Avançado mostra o centro de Validação Privada e permite baixar a planilha-modelo.

Backtest histórico, walk-forward OOS e Forward/Paper real da fase privada são evidências diferentes. O sistema não trata OOS histórico como se fosse amostra Forward/Paper.

Amostra, expectativa, drawdown, estabilidade temporal, OOS, fricção, robustez de parâmetros, regimes e sessões são analisados em conjunto. Win rate sozinho nunca qualifica um setup.

Mesmo quando os mínimos forem atingidos, o estado é apenas **pronto para revisão humana**. Promoção para o modo Iniciante continua manual.
