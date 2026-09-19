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
