# Atlas Índices v0.7 — especificação funcional consolidada

**Data-base:** 16/11/2026
**Estado:** DOCUMENTO / LAB / AGUARDAR / HARD NO-GO
**Natureza:** consolidação técnica para revisão independente, não cópia literal integral da redação anterior.
**Origem das decisões:** comunicação do proprietário e documentos de continuidade, parte relatada pelo auditor Claude.

## 1. Objetivo e prioridade

Este piloto **prioriza oito ativos agora**, para validar coleta, qualidade temporal, previsões D1 e W1 e comparação com referências simples. A redução diminui dependências iniciais, mas **não permite declarar desempenho de mercado mais cedo do que os critérios estatísticos aprovados**. Ampliação de ativos será gradativa, condicionada a validação e autorização expressa.

| Grupo | Símbolo | Instrumento e fonte planejados |
|---|---|---|
| Forex | EURUSD | Pepperstone MT5 Demo |
| Forex | GBPUSD | Pepperstone MT5 Demo |
| Forex | USDJPY | Pepperstone MT5 Demo |
| Forex | AUDUSD | Pepperstone MT5 Demo |
| Forex | USDCAD | Pepperstone MT5 Demo |
| Índices | US500 | CFD da Pepperstone relacionado ao S&P 500 |
| Índices | NAS100 | CFD da Pepperstone relacionado ao Nasdaq 100 |
| Ouro | XAUUSD | Ouro/dólar da Pepperstone |

Os resultados se aplicam somente às **séries efetivamente avaliadas**. Não extrapolar US500/NAS100 a índices à vista, contratos futuros ES/NQ ou CFDs de outros fornecedores.

O método experimental **Atlas Índices v0, com quatro fatores**, não é o **Motor A completo de 32 fatores**. O objetivo é validar uma hipótese reduzida de viés, sem trocar a arquitetura principal nem declarar o Motor A validado.

Não há operações reais ou simuladas, ordens, depósito, sinais públicos nem alteração operacional do Radar/Painel Mestre.

## 2. Observações de instrumentos e calendário

**[CONFIRMADO POR EXECUÇÃO — conforme relato do auditor Claude, não reconfirmado nesta PR]** Em 16/11/2026 o auditor observou o servidor Pepperstone-Demo, uma conta demo modo Hedge e os oito nomes sem sufixo.

**[CONFIRMADO POR EXECUÇÃO — conforme relato do auditor]**
- US500 e NAS100: modo de cálculo CFD, um dígito, tamanho de contrato 1, margem e lucro em USD; sessões do servidor de segunda a quinta 01:00–23:59, sexta 01:00–23:55, sem sessão sábado/domingo.
- XAUUSD: modo de cálculo exibido Forex, dois dígitos, contrato 100 XAU, margem XAU, lucro USD, comissão exibida de USD 3,50 por lote (custo total não verificado), sessões segunda a quinta 01:01–23:59, sexta 01:01–23:55; sem sessão sábado/domingo.
- USDCAD: um carimbo de abertura D1 foi visto às 00:00 na convenção do servidor.

**[INFERIDO]** A comparação de relógios de 16/11/2026 sugeriu UTC+2 no servidor; essa inferência não constitui medição autenticada, nem garante o offset em outra estação do ano.

**[NÃO VERIFICADO]** Início real das velas D1 de US500, NAS100, XAUUSD e quatro pares, especificações completas dos cinco pares, séries históricas H1/D1/W1 e lacunas, sincronismo do relógio, horários de feriados e mudanças de sessão, validade de conta demo.

O congelamento de previsão D1 ocorre **cinco minutos antes da abertura autenticada da vela avaliada**; W1 terá fronteira semanal própria e autenticada. Se o calendário estiver ausente ou duvidoso: **ABSTER-SE — CALENDÁRIO NÃO VERIFICADO**.

Abertura de sessão às 01:00 ou 01:01 **não comprova** que o carimbo D1 comece no mesmo minuto. A vela anterior pode ainda estar aberta cinco minutos antes da próxima D1. Só usar a última vela comprovadamente encerrada no corte.

## 3. Dados e prevenção de informação futura

Toda previsão deve registrar: ativo e contrato, período, fonte, calendário, UTC, corte, hora de captura, fatores elegíveis, versão de regra, motivos, estado ALTA/BAIXA/ABSTER-SE, lote, hash e prova de anterioridade.

Para dados econômicos, separar:
- scheduled_release_at_utc: horário previsto do anúncio;
- provider_fetched_at_utc: horário informado pelo provedor, se existente;
- capture_at_utc: instante real declarado de recebimento;
- forecast_freeze_at_utc: corte;
- source_id e hashes de recibos/fonte, quando disponíveis.

**Regra rígida:** capture_at_utc < forecast_freeze_at_utc. Horário programado não substitui horário efetivo de captura. Não usar resultado ou consenso publicado depois do corte, nem revisão posterior como dado contemporâneo.

Os lotes de **PREVISÃO** e **RESULTADO** são diferentes: o primeiro é anterior ao corte; o segundo somente após o fechamento e jamais altera o primeiro. Capturas são de acréscimo, sem sobrescrever originais; lacunas e revisões são registradas.

## 4. Quatro fatores e escore

| Fator | Peso |
|---|---:|
| Política monetária e juros (P) | 35% |
| Inflação (I) | 25% |
| Emprego e desemprego (E) | 25% |
| Atividade econômica (A) | 15% |
| **Total** | **100%** |

S = 35×P + 25×I + 25×E + 15×A. Cada sinal de fator vale +1, −1 ou 0, e poderá ser AUSENTE. Não redistribuir pesos quando faltar informação obrigatória; emitir ABSTER-SE. Emprego e desemprego requerem regra de agregação para não contar a mesma divulgação duas vezes.

**Decisão informada do proprietário:** ALTA quando S ≥ +70; BAIXA quando S ≤ −70; exigir pelo menos dois fatores não neutros concordantes com a direção. Em outros casos, ABSTER-SE. O escore **não é** uma porcentagem de confiança comprovada.

Matriz causal ainda precisa definir ativo × indicador × condição econômica × direção de impacto × tipo de fator × duração. Ouro e índices exigem regras próprias, sem presumir relação fixa entre juros, dólar e preço.

**Fator SURPRESA:** diferença entre resultado divulgado e consenso obtido **antes** do anúncio. **Fator ESTADO:** condição econômica que pode persistir. Ainda não está definido qual tipo cada fator usará e por quanto tempo será válido. EODHD e fontes públicas serão avaliados documentalmente antes da escolha.

## 5. Resultado e estabilidade

O rótulo da vela será baseado na variação percentual 100 × (fechamento − abertura)/abertura, com abertura positiva e preços autênticos. A faixa **ESTÁVEL** ainda não foi escolhida:
- A: D1 até 0,05%; W1 até 0,25%.
- B: D1 até 0,10%; W1 até 0,50%.
- C: limite próprio por ativo, definido previamente.

Previsão direcional diante de resultado ESTÁVEL não é acerto, e permanece contada. Dado ausente não equivale a ESTÁVEL.

Um estudo anterior à fase prospectiva deverá medir, para os oito ativos em D1/W1: quantidade de velas, lacunas, média e mediana de movimentos absolutos, percentis 25/50/75/90 e quantos movimentos cada faixa trataria como estáveis. Não escolher depois de olhar os resultados do piloto.

## 6. Baselines e estatística

Três baselines obrigatórios: **sempre alta**, **sempre baixa** e **repete o último período já fechado antes do corte**. O método e os baselines usam exatamente o mesmo universo de oportunidades, preços, calendário, corte e conjunto informacional; o terceiro baseline não usa a vela ainda aberta.

Registrar acertos, erros, abstenções, falhas, estabilidade e cobertura, incluindo todas as oportunidades, e comparar as previsões direcionais nas mesmas oportunidades dos baselines.

**Decisão informada do proprietário:** 52 semanas informativas, teste exato de sinais unilateral sobre diferenças semanais pareadas e Bonferroni (0,05/3 ≈ 0,0166667). Para **52 diferenças semanais não empatadas** em cada comparação, o limite é **35 semanas favoráveis** para o método em cada um dos três confrontos (p≈0,00876662, sob condições do teste). Com 34/52 p≈0,01824170 e não satisfaz esse limite.

A inferência depende de pressupostos estatísticos: semanas com autocorrelação ou outros vínculos demandam análise adicional. Oito ativos não são oito experimentos independentes, especialmente por causa de fatores macro com USD. Empates e semanas sem sinal não são apagados. Não alegar superioridade sem cobertura/integridade e resultados válidos.

As **primeiras quatro semanas** avaliam apenas funcionamento do processo. **52 semanas informativas** podem exigir mais de um ano calendário; reduzir para oito instrumentos não reduz esse horizonte por si só.

## 7. Operação planejada, não implementada

- Captura H1 + D1 + W1 por script local, somente leitura, com terminal Pepperstone aberto, após análise independente e autorização específica. Sem envio de ordens, credenciais ou arquivos pela rede pelo exportador.
- Armazenamento: computador + nuvem como segunda cópia, retenção sem prazo final definido, com verificação de hashes e restauração; fornecedor e procedimentos ainda em aberto.
- Publicação automática dos hashes de **PREVISÃO** por um sistema autorizado, sempre antes do corte, sujeito a PR específica, permissões mínimas, teste e aprovação futura. O proprietário pretende conferir uma vez por semana.
- Nenhuma operação real ou simulada neste piloto; o teste futuro de registro externo de hash foi aceito apenas **em princípio**, ainda exigindo aprovação dos detalhes.

## 8. Etapas e expansão

**Etapa 1:** fechar documentação, calendários, fonte econômica, matriz causal e escolhas 1, 3, 4.  
**Etapa 2:** implementar e auditar separadamente um exportador local H1/D1/W1, sem ordens, e o mecanismo de anterioridade se autorizado.  
**Etapa 3:** piloto prospectivo de oito ativos; quatro semanas iniciais só de verificação de processo.  
**Etapa 4:** análise com 52 semanas informativas e três baselines; verificar qualidade, cobertura e força de evidência.  
**Etapa 5:** somente após validação e nova autorização, considerar ampliar Forex 5 → 10 → 28 e índices adicionais em etapas controladas. WIN e Ibovespa somente por nova decisão.

A expansão não decorre apenas de atingir uma data. O projeto pode permanecer em oito ativos se os critérios não forem satisfeitos. Também não se reclassifica automaticamente uma taxa de acerto descritiva em prova de lucro.

## 9. Proibições e lacunas

Proibidos nesta fase: operar, simular operação, depositar, executar integração, criar workflow, fazer merge, alterar FX28, protocolos CPI/PPI ou PRs técnicas, usar dados posteriores ao corte, preencher candles, esconder abstenções ou publicar desempenho não validado.

**Três decisões principais pendentes:** (1) estabilidade A/B/C; (3) SURPRESA/ESTADO por fator; (4) duração de validade até próxima divulgação ou por N dias. Suas definições dependerão de estudo histórico, dados EODHD efetivamente acessíveis e fontes oficiais. O acesso EODHD não está autenticado.

**Aumento de escopo:** somente por deliberação posterior do proprietário, após avaliação independente do piloto.

**Estado:** DOCUMENTO / LAB / AGUARDAR / HARD NO-GO.