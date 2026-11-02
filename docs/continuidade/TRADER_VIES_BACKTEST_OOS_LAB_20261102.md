# AtlasQuant Trader — Medição histórica de viés FX: desenho OOS em LAB

**Data:** 02/11/2026. Referência: PR #1803 · Status: LAB / HARD NO-GO.
**Foco aprovado:** viés diário principal, confirmação semanal e contexto mensal,
com matriz de 28 pares, sem duplicar o script ICT/SMC do TradingView.

## O que existe nesta etapa

atlasquant_trader_bias_oos_lab.py é um avaliador **puro, sem I/O**, de
previsões e preços posteriores que o chamador fornece em simulação. Cada
previsão exige: ID único, par canônico, horizonte D1/W1/MN1, direção
ALTA/BAIXA/NEUTRO/AGUARDAR, método fixo, hora de emissão e hora-limite
de evidência já conhecida. O resultado posterior tem ID correspondente,
preços e horários distintos de entrada observacional e encerramento.

- Força/viés não constitui ponto de entrada: os preços de avaliação
  medem direção futura e NÃO equivalem a ordens, P&L ou rentabilidade.
- Regra temporal: evidencia_at <= issued_at < primeiro_preco < ultimo_preco
  <= instante_da_avaliacao. Datas sem fuso, resultados futuros, valores
  não finitos, sequências incompletas, ID duplicado/orfão ou timeframe
  incompatível rejeitam toda a amostra, evitando exclusões oportunistas.
- Corte externo *train/test*: previsão antes do corte cujo resultado
  cruza o corte é **expurgada** do treino. Apenas previsões emitidas
  depois do corte entram na avaliação fora da amostra (OOS). Nenhum
  limiar é treinado ou escolhido com dados de teste.
- A avaliação é independente para D1, W1 e MN1 e por combinação
  par/horizonte (28 x 3), sem extrapolar acerto de um par aos demais.
- Mede acertos direcionais (não lucro), proporção de previsões
  direcionais (cobertura) e abstenções neutro/aguardar; compara o
  mesmo conjunto de previsões com baseline simples "sempre alta".
  Movimento inferior à faixa de ruído experimental não vira alta/baixa.
- Sem amostra mínima de previsões direcionais, treino e diferentes
  dias de teste, o percentual de acerto **não é publicado**.
  Para produção, amostras e recortes serão bem mais rigorosos.
- Se houver mudança de método no meio da amostra, recusa a avaliação:
  não se pode juntar previsões de versões diferentes para criar
  artificialmente uma taxa de acerto.

## O que NÃO foi comprovado

Os testes usam deliberadamente estados
LAB_SYNTHETIC_BIAS / LAB_SYNTHETIC_SPOT_OUTCOME.
Carimbos e preços fornecidos por um chamador não são, por si, uma
prova de captura imutável, integridade de mercado, spread ou
ausência de contaminação. Portanto **qualquer percentual de teste é
sintético** e nunca valida assertividade real, nem predição real.

O motor de viés ainda não foi conectado ao Radar, não consome
histórico real, não sabe a veracidade da fonte e não converte
ranking em recomendação de compra/venda.

## Próximo portão obrigatório

1. Histórico de cotações autorizado, completo para 28 pares e
   todos os horários definidos, com direitos de uso e custos conhecidos.
2. Registro imutável de previsões antes de observar o resultado,
   auditar as fontes macro/políticas disponíveis naquela data.
3. Backtest point-in-time, separação OOS e walk-forward real, sem
   otimização com holdout; medir também cobertura, conflitos,
   abstinências, regimes e baselines comparáveis.
4. Verificações independentes, revisão humana e novas autorizações
   antes de qualquer integração operacional.

**Segurança:** sem API nova, cobranças, cron, Worker, deploy, merge
ou ordens reais. Não declarar resultado de mercado real pelo LAB.


## Revisão anti-inflacionamento de amostras (02/11/2026)

O backtest do **viés diário** precisa impedir que múltiplas leituras
intradiárias do MESMO par e horizonte sejam contabilizadas como
previsões independentes no mesmo dia. O avaliador LAB agora exige
unicidade de **(par, horizonte, data UTC da emissão)**:

- Diferença no ID da previsão, minuto, hora ou representação de offset
  NÃO cria uma nova observação estatística no mesmo dia UTC.
- Em vez de escolher retrospectivamente a previsão que acertou, o
  avaliador **rejeita o lote inteiro** com o código
  DUPLICATE_PAIR_HORIZON_UTC_DAY_EVALUATION_SLOT.
- Pares e horizontes diferentes podem ocupar slots independentes,
  mas seus resultados ainda são correlacionados; a contagem não
  representa ensaios estatísticos independentes e não autoriza
  intervalos de confiança ou taxas reais de acerto.
- Diariamente o motor poderá ser atualizado depois de eventos macro;
  isso NÃO significa que cada atualização possa aumentar o número
  de amostras do backtest. O horário de observação avaliável precisa
  ser predefinido e registrado ANTES de conhecer os resultados.
- A data UTC é convenção transitória de LAB, não substitui
  comprovação da sessão Forex e do calendário local de mercado.
- Cinco testes novos/ajustados cobrem duplicação de mesmo dia,
  alterações de horário/fuso, dias insuficientes e diferentes
  pares/horizontes. A suíte Quality já executa o arquivo.

**Mantido:** nenhuma previsão imutável real, preço spot licenciado,
mensuração OOS real ou porcentagem de assertividade demonstrada.
HARD NO-GO — sem merge/deploy, Worker, cron, ordens ou gasto.
