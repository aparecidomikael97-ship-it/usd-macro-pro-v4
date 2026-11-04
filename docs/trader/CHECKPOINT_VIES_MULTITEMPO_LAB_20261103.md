# AtlasQuant Trader — checkpoint de viés W1/D1/H4/M15 (LAB)

## Objetivo
Radar enxuto com 28 pares Forex e filtro direcional de quatro horizontes, sem misturar OB/FVG com o script próprio. Apenas análise, sem ordens.

## Já publicado (commit Render 186f238)
- Home Ecossistema: AtlasQuant Trader destacado, áreas antigas preservadas e cartões secundários pequenos
- Perfil com foto local ao navegador
- Trader: Início, Radar, Painel Mestre, sem Scanner Técnico na nova área
- Universo 28 pares/8 moedas, grupos de índices, WIN/WDO, explicações macro/micro/geopolítica
- Calendário EODHD preparado para leitura com credencial preexistente, condicionado à disponibilidade de dados

## Implementado apenas nesta branch LAB
- Contrato ATLASQUANT_TRADER_BIAS_MATRIX_V1
- Tabela detalhada recolhível dentro do Radar, com W1/D1/H4/M15
- Um resultado ALTA/BAIXA é exibido **somente** com quatro horizontes válidos e na mesma direção
- Divergência W1/D1, H4 contrário, M15 sem confirmação, neutralidade ou falta de carimbo => AGUARDAR
- Janelas de validade por horizonte: W1 9 dias; D1 72 horas; H4 10 horas; M15 60 minutos (limiares provisórios de laboratório)
- Daily percentual expira em 36 horas; fonte/horário obrigatórios; horário exibido em UTC correto
- Nenhuma cotação, viés ou resultado de mercado é sintetizado; status de LAB não autoriza operação

## Etapa adicional (LAB): tendência a partir de candles fechados
- Módulo `atlasquant_trader_bias_candle_research.py`: cálculo exploratório com EMA20/EMA50, inclinação e faixa de volatilidade ATR
- Exige 60 candles OHLC válidos por horizonte, fechamento explícito (`closed_at`), timestamps com fuso e janela de validade
- Recusa candle ainda aberto, data futura, série duplicada/sobreposta, OHLC incoerente, dados vencidos ou histórico insuficiente
- Produz exclusivamente `RESEARCH_ONLY` com `publishable=False`; NÃO satisfaz `VALIDATED_BIAS_EVIDENCE` sem validação externa de origem
- Cobertura potencial para os 28 pares, mas nenhuma evidência atual do fornecedor foi conectada; sem rede, custo ou operação
- Auditado cache local: somente 7 pares diários; última atualização gravada em 2026-09-17, inadequada para uso como dado atual

## O que **não** está pronto
- Alimentador real validado para W1/D1/H4/M15; nenhum cálculo de tendência a partir de séries OHLC conectado
- Prova de origem autêntica do fornecedor/validador: o contrato de entrada não substitui assinatura ou auditoria do produtor
- Força relativa atualizada das 8 moedas e Top 10 diário completos
- Feed de notícias em tempo real e dependências de API, custos e licenças ainda a definir
- Backtest fora da amostra e calibração de acerto. Alinhamento não é probabilidade de acerto

## Próxima etapa recomendada
Validar fonte gratuita/contratada já existente, disponibilidade de OHLC para 28 pares e horário/fuso. Criar validador de séries e score por estrutura de preço, usando apenas snapshots com fonte auditável; comparar comportamento em backtest e paper antes de demonstrar viés ao usuário.

## Restrições
AION congelado e HARD NO-GO; sem Worker, cron ou novo serviço; nenhuma ativação automática; Render não será atualizada por esta branch sem aprovação e checagem.
