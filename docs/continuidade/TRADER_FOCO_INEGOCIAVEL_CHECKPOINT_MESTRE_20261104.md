# ATLASQUANT TRADER — FOCO INEGOCIÁVEL DO PROPRIETÁRIO

**Checkpoint Mestre de foco — Mikael, 04/11/2026.**

Este documento é a referência de decisão para todo desenvolvimento futuro
do AtlasQuant Trader. Antes de programar um novo bloco, verificar se atende
diretamente aos itens P1/P2 abaixo. Se não atender, **não ampliar o escopo**
sem nova instrução explícita do proprietário.

## P1 — O que o Trader deve entregar

O objetivo não é gerar sinais isolados ou enfeitar indicadores. É explicar,
de forma clara e rastreável, **qual moeda está relativamente mais forte,
qual está mais fraca, por quê e em que horizonte**, com base em evidências
econômicas e acontecimentos observados.

**Universo principal:** oito moedas G8 (**USD, EUR, GBP, JPY, CHF, AUD,
CAD, NZD**) e seus **28 pares Forex**. Para cada par, analisar a moeda-base
contra a cotada com viés separado de **D1 (dia), W1 (semana) e MN1 (mês)**.
O resultado deve ser `ALTA`, `BAIXA`, `NEUTRO` ou `AGUARDAR` **somente após
comprovação suficiente**. Na pesquisa atual, vieses operacionais ficam em
`AGUARDAR` porque fontes/custódia/validação real ainda são incompletas.

**Seis prioridades em conjunto, sem pular nenhuma:**

1. Macroeconomia: inflação, emprego, atividade, bancos centrais e juros
   atuais **e esperados**, diferenciais e risco de surpresa.
2. Microeconomia: setores, produção, comércio, confiança e transmissão à
   economia e ao câmbio.
3. Geopolítica: acontecimentos com origem, data, alcance, canais de risco
   e hipóteses contrárias.
4. Notícias: fonte, publicação, última verificação, alteração e impacto
   explicativo, sem confundir rumor, expectativa e fato.
5. Calendário econômico: hora/fuso, dado anterior, consenso, real,
   revisões, alterações de programação e tempo até a divulgação.
6. Força relativa: distinguir *fundamentos macro* de *valorização
   efetivamente observada* com cotação independente, e comparar base/cotada
   sem dupla contagem de cruzamentos sintéticos.

**Saída explicativa obrigatória:** evidência favorável, evidência contrária,
lacunas, risco de evento/reversão, fontes, horários, condição de invalidação,
diferença entre viés D1/W1/MN1 e qualidade do dado. Um calendário com evento
próximo **não** dá direção sozinho.

## P2 — Frequência, custos e qualidade

- **Agora:** somente **três revisões completas por dia**, usando fontes
  gratuitas e respeitando seus termos. O planejamento pré-existente é
  06:35, 10:45 e 17:15 (Brasília), ainda **não ativado**.
- Rechecagens extras de 5 ou 15 minutos **não** são prioridade nem requisito
  ativo nesta fase; foram expressamente **adiadas**.
- **Futuro opcional:** atualização a cada **uma hora**, somente após
  avaliar custos/licenças, infraestrutura e receber autorização de Mikael.
- Precisão se mede por qualidade, frescor, auditoria e avaliações
  *out-of-sample* (OOS) por par/horizonte/regime, incluindo abstenções.
  **Ranking/score não é probabilidade**, e 90% de acerto não está provado.
- O BCE pode fornecer estudo gratuito de **taxas de referência diárias**
  das oito moedas; 21 dos 28 pares são cruzamentos derivados. A fonte **não**
  valida entrada M15, spread nem preço negociável em tempo real.
- **Sem contratação nova** e sem ativar processos/serviços externos até
  autorização. PR em LAB/DRAFT, aplicação publicada preservada.

## Não desviar o foco

- **FVG, OB, BOS, CHoCH, novos setups, gatilhos M15 ou replay de preços**:
  ficam em segundo plano; são desenvolvidos separadamente no TradingView,
  sem ocupar a prioridade macro do AtlasQuant Trader.
- **AION/Worker, deploy, ordens reais, Trader live e Render**:
  manter **HARD NO-GO**, sem usar o projeto Trader como atalho para ativação.
- **WIN/WDO e índices americanos**: continuar previstos, mas exigem
  fundamentos/modelos próprios; nunca herdar diretamente sinal Forex.
- **Aba Negócios, cursos, vídeos, hardware e expansão comercial**:
  não consumir o bloco atual do Trader sem pedido específico.
- Interface: preservar o desenho **Início, Radar, Scanner Técnico e Painel
  Mestre**, futurista, enxuto e com "Macro" como agrupador, sem aumentar
  telas por conta própria. "Poderoso por dentro. Simples por fora."

## Ordem fixa dos próximos blocos

1. Conectar fontes oficiais **sem custo**, dentro dos termos, com captura
   ponto-no-tempo, datas/horários válidos e detecção de alteração.
2. Provar as três atualizações diárias com registro auditável e comunicar
   ausência/falha/fonte desatualizada, sem afirmar "tempo real" indevidamente.
3. Completar o contexto causal das oito moedas; comparar forças por par e
   horizonte, incluindo contraprovas, notícias e geopolítica.
4. Validar dados de preço independentes e testar viés D1/W1/MN1 por
   *walk-forward* OOS; medir resultado, cobertura e calibração antes de
   propor viés operacional ou integração no Radar.
5. Somente com verificações independentes e autorização, reconsiderar
   publicação, custos, frequência horária ou integração operacional.

**Regra de execução:** toda próxima melhoria deve declarar a qual item P1/P2
ela serve, quais evidências acrescenta, quais testes passaram e quais lacunas
continuam abertas. Na ausência de vínculo direto, **pausar e perguntar**.

## Situação do checkpoint

Em 04/11/2026, PR #1803 é a revisão canônica de **laboratório**. A rodada
mais recente de testes de módulos Trader `*lab.py` alcançou **233 testes
locais aprovados** (incluindo 13 novos de verificação matemática de duas
assinaturas Ed25519 sintéticas, sem comprovação de identidade real).
Uma nova rodada de CI **não foi confirmada** para este último bloco. Os
coletores contínuos e três jobs diários **não estão ativados**. Não foi
feito merge, deploy, atualização de aplicação publicada, uso de Worker
nem cobrança. O conflito atual da PR com `main` segue sem resolução.
