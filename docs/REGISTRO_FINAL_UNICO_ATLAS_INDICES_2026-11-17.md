# ATLASQUANT ÍNDICES — REGISTRO FINAL ÚNICO

## DECISÕES DO PROPRIETÁRIO, FONTES MACROECONÔMICAS E ESTUDO D23

**Data de referência:** 17/11/2026  
**Natureza:** Consolidação documental para auditoria final  
**Documentos de origem:** Consolidação Rev 8 (D1–D34), Adendo revisado, Matriz de Cobertura Rev 5 e Tabela D23 revisada  
**Situação:** Documento textual ainda não publicado em repositório  
**Estado:** DOCUMENTO / LAB / HARD NO-GO

---

# 1. CONTEXTO E ESTADO DO PROJETO

## 1.1 Objetivo

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisões apresentadas na Consolidação Rev 8:**

O projeto AtlasQuant Índices tem como objetivo desenvolver e avaliar um motor de viés macroeconômico.

O horizonte principal da avaliação oficial é D1.

W1 e M1 permanecem exclusivamente descritivos no protocolo atual.

O piloto compreenderá oito instrumentos da Pepperstone MT5 Demo:

1. EURUSD
2. GBPUSD
3. USDJPY
4. AUDUSD
5. USDCAD
6. US500
7. NAS100
8. XAUUSD

**CONFIRMADO POR ANÁLISE ESTÁTICA — D2 e D13:**

O histórico retrospectivo será utilizado para desenvolvimento.

As quatro semanas preliminares serão destinadas à verificação técnica e não integrarão a avaliação oficial.

A avaliação confirmatória exigirá 52 semanas prospectivas e informativas.

**NÃO VERIFICADO:** O piloto oficial não foi demonstrado como iniciado ou concluído.

Nenhuma assertividade foi comprovada neste registro.

## 1.2 Papéis e responsabilidades

**CONFIRMADO POR ANÁLISE ESTÁTICA — atribuição informada pelo proprietário:**

| Participante | Responsabilidade |
|---|---|
| Proprietário | Decide, aprova, autoriza ou rejeita todas as mudanças |
| ChatGPT | Constrói e organiza o projeto; é o único agente designado pelo proprietário para escrever no GitHub e no Render, exclusivamente mediante autorização |
| Claude | Auditor independente das decisões, documentos, evidências e resultados |

**INFERIDO:** A atribuição de responsabilidade não concede autorização automática de acesso, edição, publicação ou execução.

## 1.3 Limites desta consolidação

**CONFIRMADO POR ANÁLISE ESTÁTICA — restrições expressas do proprietário:**

- Não acessar GitHub, Render, MT5 ou EODHD.
- Não criar conta, chave, senha ou token.
- Não modificar o Checkpoint Mestre.
- Não modificar revisões documentais fechadas.
- Não criar branch, commit, PR ou merge.
- Não iniciar trading real ou simulado.
- Não executar integração ou deploy.
- Não publicar este documento antes de autorização.

A futura PR documental somente poderá ser aberta após o proprietário escrever expressamente:

**"pode abrir a PR"**

**Sem execução nesta tarefa:** Este registro não apresenta nova execução operacional.

**NÃO VERIFICADO:** Não houve reconferência independente do estado dos sistemas externos nesta tarefa.

---

# 2. DECISÕES CONFIRMADAS DEPOIS DA CONSOLIDAÇÃO REV 8

## 2.a — D25: previsão ALTA ou BAIXA dentro da faixa ESTÁVEL

**CONFIRMADO POR ANÁLISE ESTÁTICA — confirmação escrita relatada pelo proprietário:**

**Data:** 17/11/2026  
**Horário:** 16h14, Campo Grande, UTC-4

Texto atribuído ao proprietário:

> confirmo: previsão de alta ou baixa com preço dentro da faixa conta como erro, para o Atlas e para os comparadores

### Aplicação

**INFERIDO — consequência direta da confirmação:**

Quando o Atlas prevê ALTA ou BAIXA e o preço permanece dentro da faixa ESTÁVEL do ativo:

- O Atlas recebe ERRO.
- Os três comparadores recebem ERRO.
- A observação permanece no universo comum, exceto quando o movimento é exatamente zero, situação resolvida posteriormente pelo proprietário.

**CONFIRMADO POR ANÁLISE ESTÁTICA:** A confirmação escrita encerra a pendência documental do complemento da D25.

**NÃO VERIFICADO:** Os limites numéricos das faixas ESTÁVEIS por ativo permanecem sem aprovação.

## 2.b — Pergunta 2: opção A — ESTADO

**CONFIRMADO POR ANÁLISE ESTÁTICA — escolha escrita relatada pelo proprietário:**

**Data:** 17/11/2026  
**Horário:** 16h28, Campo Grande

Foi escolhida a opção A da Pergunta 2.

### Regra

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

Utilizar ESTADO para:

- Inflação.
- Emprego.
- Atividade econômica.

A política monetária já utiliza ESTADO conforme D19.

**INFERIDO:** Os quatro fatores macroeconômicos passam a seguir a diretriz geral de ESTADO.

### Ausência de dado

**CONFIRMADO POR ANÁLISE ESTÁTICA — D22:**

Quando faltar o dado necessário, o Atlas deverá ABSTER-SE.

Não serão inventados resultados, expectativas ou valores.

### Valores históricos

**CONFIRMADO POR ANÁLISE ESTÁTICA — escolha do proprietário:**

A leitura anterior deverá utilizar o valor efetivamente publicado na época, não o valor revisado posteriormente.

**NÃO VERIFICADO:** A existência de todas as versões históricas originais nas fontes ainda não foi demonstrada.

### Limites numéricos

**NÃO VERIFICADO — PENDENTE DE ESTUDO E APROVAÇÃO:**

Os parâmetros que definirão condições como ALTO, BAIXO e SUBINDO dependerão de estudo histórico e aprovação do proprietário antes do congelamento.

Nenhum valor é escolhido aqui.

### Consenso pago

**CONFIRMADO POR ANÁLISE ESTÁTICA — D6 e decisão posterior:**

Consenso pago permanece fora do protocolo atual.

Sua eventual utilização exigirá decisão separada e avaliação nova.

**Estado da Pergunta 2: RESPONDIDA — OPÇÃO A.**

## 2.c — D27: cobertura mínima e semana informativa

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisão escrita relatada:**

**Data:** 17/11/2026  
**Horário:** 17h51, Cuiabá, UTC-4

Foi aceita a opção A.

### Definição de cobertura

**INFERIDO — representação matemática da decisão:**

Cobertura (%) = número de observações possíveis com previsão válida e hash válido antes do corte / número total de observações possíveis da semana × 100.

O universo possível considera:

- Os ativos do piloto.
- Os dias com mercado aberto.
- A disponibilidade dos dados necessários.

### Previsão válida para a cobertura

**CONFIRMADO POR ANÁLISE ESTÁTICA — texto presente no Adendo revisado, seção 4.1:**

O Adendo registra, sob o rótulo **INFERIDO — esclarecimento da cobertura**:

> ABSTER-SE não conta como previsão válida para a cobertura.

> Bloqueio por horário incerto não conta como previsão válida para a cobertura.

> Falha técnica não conta como previsão válida para a cobertura.

> Previsão ESTÁVEL com hash válido antes do corte conta como previsão válida para a cobertura, desde que cumpra os demais requisitos de validade, mesmo quando a observação posteriormente ficar fora da conta de acertos pela D25.

**INFERIDO — conforme classificação atribuída no próprio Adendo:** A previsão ESTÁVEL com hash válido antes do corte conta como previsão válida para a cobertura, respeitados os demais requisitos.

**NÃO VERIFICADO:** Esta revisão não demonstra implementação operacional nem confirmação independente adicional dessa interpretação.

**INFERIDO:** Contar uma previsão como válida para cobertura não significa necessariamente incluí-la na pontuação de acertos.

### Piso percentual

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

O piso será único e percentual.

**50% é apenas provisório.**

**NÃO VERIFICADO:** O valor definitivo não foi aprovado.

O piso final dependerá do estudo histórico de abstenções, do estudo de poder estatístico D29 e da aprovação do proprietário.

### Semana abaixo do piso

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

A semana abaixo do piso:

- Não contará entre as 52 semanas informativas.
- Terá seu resultado publicado separadamente.
- Não poderá ser descartada silenciosamente.
- Consumirá tempo dentro do prazo máximo previsto na D34.

Falha técnica permanecerá classificada separadamente, conforme D27 e D32.

## 2.d — D28: baseline de repetição do dia anterior

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisão escrita relatada:**

**Data:** 17/11/2026  
**Horário:** 17h53, Cuiabá

Foi aceita a opção A.

### Definição operacional

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

- "Dia anterior" significa a sessão anterior do próprio ativo.
- A identificação da sessão dependerá da tabela D23.
- A direção será obtida pelo candle D1 fechado.
- Se o candle apresentar movimento exatamente zero, procurar a última sessão com movimento.
- O limite de retrocesso é provisoriamente de cinco sessões.
- No começo do teste oficial, poderão ser utilizados candles históricos reais anteriores ao início do teste.
- Candle indisponível ou limite excedido exclui a observação da pontuação dos quatro métodos.
- Sessão curta poderá contar se houver candle D1 válido, com a condição devidamente sinalizada.

**NÃO VERIFICADO:** O limite definitivo de retrocesso ainda não foi aprovado.

## 2.e — Elegibilidade das observações

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisão escrita de 17/11/2026, 17h56, Cuiabá:**

Cada observação representa um ativo em um dia.

A classificação deverá respeitar a seguinte ordem fixa, sendo cada observação atribuída a uma única categoria.

| Ordem | Situação | Tratamento |
|---|---|---|
| **1** | Falha técnica: hash inválido, preço ou dado ausente, previsão fora do prazo | Fora da conta para os quatro métodos; registrada como falha técnica e considerada na validade da semana |
| **2** | Horário incerto, conforme D23 | Fora da conta dos quatro métodos; registrado como bloqueio |
| **3** | Atlas se abstém, conforme D18, D19 ou D22 | Fora da conta dos quatro métodos |
| **4** | Baseline de repetição não consegue emitir previsão | Fora da conta dos quatro métodos |
| **5** | Movimento exatamente zero | Fora da conta para os quatro métodos, sem exceção |
| **6** | Atlas prevê ESTÁVEL e o preço fica dentro da faixa ESTÁVEL | Fora da conta dos quatro métodos |
| **7** | Atlas prevê ESTÁVEL e o preço fica fora da faixa ESTÁVEL | Erro do Atlas; comparadores pontuam normalmente |
| **8** | Atlas prevê ALTA ou BAIXA e o preço fica dentro da faixa ESTÁVEL | Erro do Atlas e dos comparadores |
| **9** | Preço fora da faixa ESTÁVEL e direção correta | Acerto |
| **10** | Preço fora da faixa ESTÁVEL e direção errada | Erro |

### Regras de apoio

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

- Uma previsão por ativo por dia.
- Considerar o primeiro hash válido publicado antes do corte.
- Previsões adicionais serão ignoradas e relatadas.
- A nota semanal é a contagem bruta dos acertos elegíveis, conforme D26.
- As observações pontuadas pertencem às categorias 7 a 10.
- `N` representa a quantidade dessas observações.
- Os quatro métodos deverão utilizar o mesmo universo.
- O relatório semanal deverá apresentar a quantidade de observações de cada categoria e a cobertura.
- Falha técnica e bloqueio não contam como abstenção.

**INFERIDO:** A categoria 5 deverá aparecer expressamente também na descrição da cobertura e da elegibilidade do futuro arquivo final.

**NÃO VERIFICADO:** A implementação dessas regras no Motor A ainda não foi demonstrada.

## 2.f — P4 e complementos de D20: resolvidos

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisão escrita relatada:**

**Data:** 17/11/2026  
**Horário:** 17h58, Cuiabá, UTC-4

Texto do proprietário:

> P4: sai da conta; D20: sim e sim

### P4

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

Movimento exatamente zero fica fora da conta, inclusive depois de previsão ALTA ou BAIXA.

**INFERIDO:** A exclusão vale simultaneamente para os quatro métodos, conforme o universo comum de D18.

A D7 trata de empates entre diferenças semanais e não da classificação do candle exatamente parado.

**Estado de P4: RESOLVIDO.**

### D20 — complemento 1

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

Os relatórios descritivos W1 e M1 serão produzidos sem custo extra.

**NÃO VERIFICADO:** A viabilidade operacional dessa condição ainda não foi demonstrada.

### D20 — complemento 2

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

Se W1 ou M1 vierem a ser utilizados como horizonte de avaliação oficial, será necessária avaliação nova, identificada e com regras previamente congeladas.

**Estado dos dois complementos de D20: CONFIRMADOS POR ESCRITO.**

## 2.g — D21: fontes macroeconômicas preliminares

**CONFIRMADO POR ANÁLISE ESTÁTICA — Matriz Rev 5 e relato das aceitações por voz em 17/11/2026:**

A escolha preliminar de fontes principais e reservas foi registrada para seis economias e quatro fatores.

**NÃO VERIFICADO:** As fontes ainda não foram aprovadas definitivamente e não passaram por teste de captura.

### Estados Unidos

| Fator | Principal preliminar | Reserva preliminar |
|---|---|---|
| Política monetária | Federal Reserve — FOMC, faixa-alvo | NY Fed — taxa efetiva |
| Inflação | BLS — CPI | BEA — PCE |
| Emprego | BLS — Employment Situation | Sem reserva |
| Atividade | BEA — PIB | Census Bureau — vendas no varejo |

### Zona do euro

| Fator | Principal preliminar | Reserva preliminar |
|---|---|---|
| Política monetária | BCE — Portal de Dados | Comunicado do BCE |
| Inflação | Eurostat — HICP | Portal de Dados do BCE |
| Emprego | Eurostat — desemprego | Portal do BCE, somente se republicar |
| Atividade | Eurostat — PIB | Portal do BCE, somente se republicar |

### Reino Unido

| Fator | Principal preliminar | Reserva preliminar |
|---|---|---|
| Política monetária | Bank of England — Bank Rate, IADB | Comunicado do MPC |
| Inflação | ONS — CPI | Sem reserva |
| Emprego | ONS — mercado de trabalho | Sem reserva |
| Atividade | ONS — PIB | Sem reserva |

### Japão

| Fator | Principal preliminar | Reserva preliminar |
|---|---|---|
| Política monetária | BoJ — API de séries temporais | Comunicado do BoJ |
| Inflação | Statistics Bureau via e-Stat — CPI | Sem reserva |
| Emprego | e-Stat — força de trabalho | Sem reserva |
| Atividade | Cabinet Office / ESRI — PIB | Sem reserva |

### Austrália

| Fator | Principal preliminar | Reserva preliminar |
|---|---|---|
| Política monetária | RBA — cash rate, Tabela F1 | Comunicado do RBA |
| Inflação | ABS — CPI | Sem reserva |
| Emprego | ABS — Labour Force | Sem reserva |
| Atividade | ABS — Contas Nacionais | Sem reserva |

### Canadá

| Fator | Principal preliminar | Reserva preliminar |
|---|---|---|
| Política monetária | Bank of Canada — API Valet | Comunicado do Banco do Canadá |
| Inflação | Statistics Canada — CPI | Sem reserva |
| Emprego | Statistics Canada — força de trabalho | Sem reserva |
| Atividade | Statistics Canada — PIB | Sem reserva |

### Condições comuns

**CONFIRMADO POR ANÁLISE ESTÁTICA — D21 e D22:**

- Nenhuma fonte é definitiva.
- A seleção final depende da cobertura e dos testes de captura.
- Onde faltar reserva e o dado necessário estiver indisponível, o Atlas deverá ABSTER-SE.
- FRED permanece exclusivamente como espelho de histórico, nunca como fonte principal.

**NÃO VERIFICADO:**

- Latência real das fontes.
- Disponibilidade anterior aos cortes.
- Captura operacional.
- Licenças completas aplicáveis ao uso pretendido.
- Equivalência dos indicadores alternativos.

---

# 3. ESTUDO 1 — D23: FUSOS E SESSÕES

## ESTADO DOCUMENTAL: FECHADO

**CONFIRMADO POR ANÁLISE ESTÁTICA — relato do proprietário:** O Estudo 1 D23 foi considerado fechado documentalmente após auditoria, com pendências de medição complementar registradas separadamente.

**NÃO VERIFICADO:** O fechamento documental não comprova a conclusão das medições históricas de fuso nem autoriza uso operacional sem as verificações exigidas.

### A) Tabela D23 — oito ativos

**Período analisado:** 03/11/2025 a 17/11/2026.

**Origem das evidências:** execução relatada do auditor Claude sobre arquivos exportados pelo proprietário e leituras de tela realizadas pelo proprietário.

**Legenda:**

- CE = CONFIRMADO POR EXECUÇÃO.
- CAE = CONFIRMADO POR ANÁLISE ESTÁTICA.
- INF = INFERIDO.
- NV = NÃO VERIFICADO.

| Ativo | Fuso do servidor e horário de verão | Sessão no horário do servidor | Dias úteis sem candle | Sexta-Feira Santa, 03/04/2026 | Observações e evidência |
|---|---|---|---|---|---|
| **EURUSD** | CE: GMT+2 exibido. CAE: GMT+3 no verão dos EUA, conforme Pepperstone. INF: deslocamento histórico | CE: seg.–qui. 00:01–23:59; sex. 00:01–23:55 | CE: 25/12/2025 e 01/01/2026 | CE: candle presente, 40.392 ticks | CE: transições sazonais conferidas, sem candle extra ou lacuna. CE: candle de 18/11/2026 presente, com 1.616 ticks |
| **GBPUSD** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 00:01–23:59; sex. até 23:55 | CE: mesmas duas datas | CE: candle presente, volume baixo | CE: candle de 18/11/2026 presente, com 2.818 ticks. CE: transições sazonais verificadas por calendário, sem lacunas ou duplicações; horários individuais não verificados |
| **USDJPY** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 00:01–23:59; sex. até 23:55 | CE: mesmas duas datas | CE: candle presente, volume baixo | CE: 17/11 teve 83.071 ticks; candle de 18/11 ausente. NV: causa da ausência. CE: transições sazonais verificadas por calendário; horários individuais não verificados |
| **AUDUSD** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 00:01–23:59; sex. até 23:55 | CE: mesmas duas datas | CE: candle presente, volume baixo | CE: candle de 18/11 presente, com poucos ticks. CE: transições sazonais verificadas por calendário; horários individuais não verificados |
| **USDCAD** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 00:01–23:59; sex. até 23:55 | CE: mesmas duas datas | CE: candle presente, volume baixo | CE: candle de 18/11 presente, com poucos ticks. CE: transições sazonais verificadas por calendário; horários individuais não verificados |
| **US500** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 01:00–23:59; sex. até 23:55; intervalo 00:00–01:00 | CE: mesmas duas datas | CE: candle presente, volume baixo | CE: transições sazonais conferidas. INF: seis datas identificadas com aparência de feriado ou sessão reduzida; outras datas também tiveram volume baixo |
| **NAS100** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 01:00–23:59; sex. até 23:55; intervalo 00:00–01:00 | CE: mesmas duas datas | CE: candle presente, volume baixo | CE: candle de 18/11 com apenas 1 tick. NV: causa. CE: transições sazonais verificadas por calendário; horários individuais não verificados |
| **XAUUSD** | CE: GMT+2 exibido. CAE: regra GMT+3. INF: histórico | CE: seg.–qui. 01:01–23:59; sex. até 23:55; intervalo 00:00–01:01 | CE: 25/12/2025 e 01/01/2026 | CE: sem candle | CE: transições sazonais conferidas; 18/11 sem candle no momento da exportação |

**CONFIRMADO POR EXECUÇÃO — conforme auditoria relatada:** Nos oito ativos, não foram encontrados candles duplicados, datas fora de ordem, candles de sábado ou domingo, nem máximas e mínimas incompatíveis com abertura e fechamento.

**CONFIRMADO POR ANÁLISE ESTÁTICA:** Leitura de tela do proprietário (MT5, Especificação → Sessões), conferida pelo auditor contra a página da Pepperstone.

**CONFIRMADO POR ANÁLISE ESTÁTICA:** Os horários de sessão relatados coincidem com a documentação da Pepperstone examinada pelo auditor.

### Ressalva sobre as transições de horário de verão

**CONFIRMADO POR EXECUÇÃO — auditor Claude:** Para GBPUSD, USDJPY, AUDUSD, USDCAD e NAS100, foi conferida a presença dos cinco dias úteis nas semanas de mudança de horário de março e outubro/novembro de 2026.

A verificação confirmou ausência de dias faltantes, candles duplicados e candles de fim de semana nessas semanas.

**NÃO VERIFICADO:** Essa conferência foi de calendário, não dos horários individuais de abertura de cada candle. Portanto, não comprova o deslocamento UTC histórico do servidor.

### B) Regra para candles D1

**INFERIDO — tratamento documental derivado da D23:**

1. Somente candles de dias já encerrados serão considerados.
2. O candle do dia corrente será descartado.
3. Um tick isolado não comprova um dia completo de negociação e não contará como dia válido.

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisão posterior do proprietário em 17/11/2026, aceita por voz:**

4. Não serão criados candles artificiais para preencher dias sem negociação. Dia sem candle ficará fora da conta.

**Estado do item B.4: DECIDIDO PELO PROPRIETÁRIO EM 17/11/2026.**

**CONFIRMADO POR EXECUÇÃO:** A exportação apresentou candles de 18/11/2026 em EURUSD, GBPUSD, AUDUSD e USDCAD com poucos ticks. NAS100 apresentou apenas um tick.

**CONFIRMADO POR EXECUÇÃO:** O candle de 17/11/2026 do USDJPY apresentou 83.071 ticks. Não houve candle de 18/11 nesse arquivo.

**CONFIRMADO POR EXECUÇÃO — correção do auditor:** O volume de 83.071 ticks não demonstra que o candle de 17/11 estava incompleto. Foram observados outros dias com volumes entre aproximadamente 76 mil e 90 mil ticks, incluindo 25/05/2026 e 20/07/2026.

**NÃO VERIFICADO:** A causa da ausência do candle de 18/11/2026 no USDJPY.

**INFERIDO:** A presença dos registros de 18/11 em outros instrumentos é compatível com a exportação realizada enquanto a sessão ainda estava em andamento.

**INFERIDO — relato da leitura de tela pelo proprietário:** O horário 00:00 dos candles D1 foi observado pelo proprietário no MT5, mas não foi confirmado diretamente pelos arquivos CSV.

**NÃO VERIFICADO PELO CSV:** Os arquivos exportados contêm somente a data dos candles, sem o horário.

### C) Horário incerto — critérios de bloqueio D23

**INFERIDO — critérios documentais de bloqueio:**

| Situação | Tratamento |
|---|---|
| Data sem evidência temporal suficiente | BLOQUEAR |
| Divergência não resolvida entre documentação da Pepperstone e MT5 | BLOQUEAR |
| Semana de mudança de horário de verão não resolvida | BLOQUEAR |
| Timestamp que não possa ser reproduzido ou auditado | BLOQUEAR |

**NÃO VERIFICADO:** A implementação desses bloqueios no sistema.

### D) Pendências e medições complementares

| Item | Estado |
|---|---|
| Deslocamento real GMT/UTC do servidor em datas históricas | **NÃO VERIFICADO — medição complementar necessária** |
| Horários efetivos dos dias de sessão curta | **NÃO VERIFICADO — medição complementar necessária** |
| Calendários oficiais de feriados aplicáveis aos índices e ao ouro | **NÃO VERIFICADO — consulta complementar necessária** |
| Responsável por executar as medições complementares | **CONFIRMADO POR ANÁLISE ESTÁTICA — decidido: proprietário realiza leituras** |
| Suficiência do período histórico disponível | **CONFIRMADO POR ANÁLISE ESTÁTICA — 12 meses suficientes por ora, sujeitos à D29** |
| Tratamento semanal definitivo das sessões dos oito instrumentos | **NÃO VERIFICADO** |
| Conversão histórica reproduzível de cada sessão para UTC | **NÃO VERIFICADO** |

#### Datas com aparência de feriado ou sessão reduzida no US500

**CONFIRMADO POR EXECUÇÃO:** Foram identificadas seis datas com volume reduzido e aparência de feriado ou sessão curta:

- 27/11/2025
- 28/11/2025
- 24/12/2025
- 26/12/2025
- 03/04/2026
- 25/05/2026

**CONFIRMADO POR EXECUÇÃO:** Essa lista não representa todas as datas de volume baixo do US500.

Outros dias também apresentaram menos de 30 mil ticks, incluindo:

- 22/12/2025
- 23/12/2025
- 29/12/2025
- 30/12/2025
- 31/12/2025

**INFERIDO:** As seis datas destacadas podem estar associadas a feriados ou sessões reduzidas.

**NÃO VERIFICADO:** A classificação oficial de cada data como feriado ou sessão curta. Volume reduzido, isoladamente, não comprova redução de horário de negociação.

### E) Limitações da D23

**NÃO VERIFICADO:** O deslocamento histórico do servidor e os horários reais das sessões excepcionais ainda não têm comprovação suficiente para conversão temporal integral.

**INFERIDO:** A existência de candle não comprova sessão normal. Os registros de 18/11/2026 devem ser avaliados conforme o encerramento efetivo da sessão, sem presumir que todos estavam completos.

**NÃO VERIFICADO:** A tabela D23 ainda não demonstra todos os requisitos para uso operacional no piloto.

### Três decisões posteriores do proprietário sobre D23

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisões relatadas pelo proprietário como aceitas individualmente por voz com "Aceito", em 17/11/2026.**

**NÃO VERIFICADO:** O horário exato de cada uma das três aceitações não foi fornecido.

#### Decisão sobre medições complementares

O proprietário fará as leituras no próprio MT5 e nas páginas oficiais da corretora, abrangendo:

- Calendários oficiais de feriados aplicáveis aos índices e ao ouro.
- Horários reais dos dias de sessão curta.
- Deslocamento histórico do servidor nas datas relevantes.

**INFERIDO — distribuição de responsabilidades:**

- O proprietário lê e fornece as evidências.
- O ChatGPT organiza os dados recebidos.
- O Claude audita sem acessar o computador do proprietário.

**NÃO VERIFICADO:** Essas medições complementares ainda não foram demonstradas como concluídas.

As leituras feitas pelo proprietário deverão ser classificadas como relato de tela, não como execução independente do auditor.

#### Decisão sobre histórico

**CONFIRMADO POR ANÁLISE ESTÁTICA — escolha relatada:**

O histórico de aproximadamente 12 meses, de novembro de 2025 a novembro de 2026, é suficiente por enquanto.

Se o estudo de poder estatístico D29 demonstrar necessidade de mais histórico, a suficiência será reavaliada.

**NÃO VERIFICADO:** Não foi demonstrado, nesta tarefa, que 12 meses atendem ao poder estatístico exigido.

#### Decisão sobre candles artificiais

**CONFIRMADO POR ANÁLISE ESTÁTICA — aceite relatado:**

Não serão criados candles artificiais.

Dia sem candle ficará fora da conta.

Essa decisão substitui a pendência anteriormente indicada no item B.4.

### Evidências consolidadas da auditoria D23

**CONFIRMADO POR EXECUÇÃO — resultados atribuídos à auditoria Claude dos oito arquivos D1:**

- Os oito arquivos foram conferidos quanto ao calendário, duplicações, fins de semana e consistência OHLC.
- As semanas de mudança de horário foram examinadas quanto à integridade do calendário, sem comprovação dos horários individuais dos candles.
- Todos os oito ativos não apresentaram candle em 25/12/2025 e 01/01/2026.
- Em 03/04/2026, somente XAUUSD não apresentou candle entre os oito ativos.
- USDJPY não apresentou candle de 18/11/2026.
- NAS100 apresentou candle de 18/11/2026 com apenas um tick.
- O volume de 83.071 ticks do USDJPY em 17/11/2026 não demonstra candle incompleto.

**NÃO VERIFICADO:** As causas das anomalias de 18/11 em USDJPY e NAS100 permanecem desconhecidas.

**Estado do Estudo 1: FECHADO DOCUMENTALMENTE, com medições complementares não executadas.**

---

# 4. CORREÇÕES DOCUMENTAIS CONSOLIDADAS

**INFERIDO — tratamento das inconsistências identificadas pelo proprietário:**

As correções abaixo são registradas para o futuro arquivo final.

Não são alterações nos documentos fechados.

## 4.1 Correções de texto e de registro

### Correção 1 — título da seção 8 da Rev 8

**CONFIRMADO POR ANÁLISE ESTÁTICA:**

O título anterior era:

"ALTERAÇÕES DA REVISÃO 7 EM RELAÇÃO À REVISÃO 6".

Para o registro atualizado, a referência correta será:

"ALTERAÇÕES DA REVISÃO 8 EM RELAÇÃO À REVISÃO 7".

**NÃO VERIFICADO:** Nenhuma edição do arquivo fechado foi executada.

### Correção 2 — confirmação escrita e ambiguidade

**CONFIRMADO POR ANÁLISE ESTÁTICA — registro apresentado anteriormente:**

Nas referências correspondentes à seção 8, item 3, e à seção 9, item 4, da Consolidação Rev 8, foi solicitada a redação:

**"ambiguidade da voz resolvida pela confirmação escrita"**

em lugar de "sem ambiguidade".

**INFERIDO — conforme correção relatada pelo auditor:** A referência à ambiguidade resolvida por confirmação escrita diz respeito à D25, confirmada pelo proprietário às 16h14, e não à D33.

**NÃO LOCALIZADO — auditor confere:** Não foi localizado o texto literal da seção 8, item 3, nem o da seção 9, item 4, da Rev 8 para comprovar diretamente a qual decisão cada expressão se refere.

Por essa razão, a atribuição à D25 permanece identificada como INFERIDO até a conferência dos trechos originais.

**CONFIRMADO POR ANÁLISE ESTÁTICA — Adendo revisado, seção 2.1:** O complemento da D25 foi registrado como confirmado por escrito.

**NÃO VERIFICADO:** O procedimento principal de dependência temporal da D33 ainda não foi escolhido, conforme a seção 5.3 deste documento.

### Correção 3 — rótulo de ausência de execução no Adendo

**CONFIRMADO POR ANÁLISE ESTÁTICA — Adendo revisado, seção 1.3:**

O trecho localizado é:

**"Sem execução nesta tarefa: Este adendo não apresenta resultados novos de execução."**

Essa ocorrência já está corrigida.

**CONFIRMADO POR ANÁLISE ESTÁTICA — Adendo revisado, seção ENCERRAMENTO DO ADENDO:**

Permaneceu a expressão antiga:

**"CONFIRMADO POR EXECUÇÃO — NÃO APLICÁVEL: Nenhum resultado novo de execução é reivindicado."**

Portanto, o problema não está integralmente corrigido no Adendo.

**Estado: AINDA A APLICAR NO ARQUIVO FINAL — somente na ocorrência remanescente do encerramento.**

A redação pretendida é:

**"Sem execução nesta tarefa: Nenhum resultado novo de execução é reivindicado."**

Nenhuma edição do Adendo fechado foi realizada nesta tarefa.

### Correção 4 — movimento exatamente zero

**CONFIRMADO POR ANÁLISE ESTÁTICA — Adendo revisado, seção 6.1, linha da categoria 5 da tabela:**

Trecho localizado:

**"5 | Movimento exatamente zero | Fora da conta para os quatro métodos, sem exceção."**

**Estado: JÁ CORRIGIDO NO ADENDO REVISADO, SEÇÃO 6.1.**

A regra também foi reproduzida na seção 2.e deste Registro Final.

**NÃO VERIFICADO:** A numeração física da linha no arquivo final não está disponível; a localização documental confirmada é a seção 6.1, categoria 5.

Não foi identificada, nas seções correspondentes do Adendo revisado apresentado nesta conversa, uma ressalva posterior que reabra P4.

### Correção 5 — Matriz Rev 5, item 78 e P4

**CONFIRMADO POR ANÁLISE ESTÁTICA — Adendo revisado, seção 8.4:**

Trecho localizado:

**"O item 78 da lista de NÃO VERIFICADO encontra-se desatualizado quanto à confirmação escrita do complemento da D25."**

A confirmação escrita foi relatada às 16h14 de 17/11/2026.

**CONFIRMADO POR ANÁLISE ESTÁTICA — Adendo revisado, seção 8.5:**

Trecho localizado:

**"P4 está resolvido. Toda observação com movimento exatamente zero fica fora da conta dos quatro métodos, sem exceção."**

Portanto:

- A situação de D25 está corretamente registrada no Adendo como confirmada por escrito.
- A situação de P4 está corretamente registrada no Adendo como resolvida.
- A Matriz Rev 5 original continua contendo as referências antigas.

**Estado: JÁ REGISTRADO NO ADENDO, SEÇÕES 8.4 E 8.5; AINDA A APLICAR NO ARQUIVO FINAL DA MATRIZ REV 5.**

Nenhuma alteração da Matriz fechada foi realizada nesta tarefa.

### Correção 6 — BCE, página de visão geral

**CONFIRMADO POR ANÁLISE ESTÁTICA — informação adicional fornecida pelo proprietário:**

O auditor conseguiu abrir a página de visão geral da API do BCE.

Assim, a afirmação anterior de que essa página específica retornou HTTP 503 está incorreta.

**INFERIDO — correção para o Registro Final:**

A página de visão geral da API foi acessada pelo auditor.

**NÃO VERIFICADO:** Isso não comprova automaticamente que todos os endpoints do BCE estavam disponíveis nem que a captura operacional funcionou.

A situação de cada endpoint deve permanecer separada.

### Correção 7 — Statistics Canada, atribuição

**CONFIRMADO POR ANÁLISE ESTÁTICA — Matriz Rev 5:**

A seção 6.3 registrou a existência da Open Licence da Statistics Canada, com condições de atribuição.

A seção 7.3.14 registrou como não verificados os requisitos específicos de atribuição e acesso da WDS na leitura adicional.

**INFERIDO — correção de precisão:**

A informação sobre a licença geral deverá ser separada da comprovação de sua aplicação exata a cada conteúdo, serviço e formato de acesso.

**NÃO VERIFICADO:** A atribuição específica exigida para todos os usos pretendidos da WDS permanece sem reconciliação documental.

**NÃO LOCALIZADO — auditor confere:** O texto exato da correção adicional pretendida pelo auditor para a inconsistência de atribuição da Statistics Canada não foi apresentado integralmente nesta conversa.

Nenhuma condição de licença adicional é presumida.

### Correção 8 — Eurostat, nota de rodapé E6

**CONFIRMADO POR ANÁLISE ESTÁTICA — Matriz Rev 5:**

A fonte E6 foi identificada como página oficial de licença, copyright e exceções do Eurostat:

https://ec.europa.eu/eurostat/help/copyright-notice

**NÃO VERIFICADO:** A página de termos não foi aberta na leitura adicional relatada pelo auditor.

**INFERIDO — nota documental:**

A referência E6 não deve ser interpretada isoladamente como comprovação integral das condições de reutilização aplicáveis ao AtlasQuant.

**NÃO LOCALIZADO — auditor confere:** O texto exato da nota de rodapé E6 solicitada pelo auditor não foi fornecido integralmente nesta conversa.

Não foi inventada uma condição de licença para preencher essa lacuna.

---

# 5. PENDÊNCIAS ABERTAS E ORDEM DE PRIORIDADE

## 5.1 P1 — contas e chaves

**NÃO VERIFICADO — decisão do proprietário ainda pendente:**

O proprietário decidirá sobre eventuais cadastros para:

- BLS v2.
- BEA.
- e-Stat.
- ABS.

**CONFIRMADO POR ANÁLISE ESTÁTICA — restrição apresentada:**

O proprietário será responsável pela criação de eventuais contas.

Essa etapa somente será considerada antes do estudo de captura e mediante autorização.

Chaves e credenciais nunca serão colocadas no chat.

Nenhuma conta ou chave foi criada nesta tarefa.

## 5.2 P2 — User-Agent da ONS

**NÃO VERIFICADO — decisão do proprietário ainda pendente:**

Definir a organização e o contato de projeto que aparecerão no User-Agent exigido pela ONS.

Não utilizar contato pessoal.

Essa definição somente será necessária antes do estudo de captura, mediante autorização.

## 5.3 Estudos futuros — todos dependem de autorização

**NÃO VERIFICADO:** Os seguintes trabalhos não foram demonstrados como concluídos ou aprovados definitivamente:

| Tema | Dependência |
|---|---|
| D24 — Faixa ESTÁVEL | Estudo histórico, valores por ativo e aprovação |
| D29 — Poder estatístico | Estudo de poder e mínimo de diferenças efetivas |
| D33 — Dependência temporal | Escolha de procedimento principal e congelamento |
| D31 — Hash e corte | Serviço, horário de corte e auditoria |
| D32 — Reinícios | Limites de reinício e duração preliminar |
| D34 — Prazo máximo | Limite de calendário e semanas invalidadas |
| D27 — Cobertura | Piso percentual definitivo |
| D28 — Repetição | Limite definitivo de retrocesso |
| ESTADO macro | Limiares numéricos históricos |
| D30 — IUT | Auditoria e registro formal do texto estatístico |
| Checkpoint Mestre, seção 8.3 | Reconciliação documental |

**CONFIRMADO POR ANÁLISE ESTÁTICA — decisões existentes:**

O princípio IUT foi confirmado pelo proprietário, mas sua redação formal ainda depende de auditoria e publicação autorizada.

O procedimento principal de dependência temporal ainda não foi escolhido.

**NÃO VERIFICADO:** A existência e a disponibilidade operacional de um Deploy Hook não foram demonstradas.

**NÃO VERIFICADO:** A causa das falhas anteriores do Production Browser Smoke não foi estabelecida por leitura de logs.

**INFERIDO — condição registrada:** Esses assuntos permanecem estacionados, fora do escopo da presente consolidação.

## 5.4 Ordem de prioridade

**CONFIRMADO POR ANÁLISE ESTÁTICA — ordem informada pelo proprietário:**

1. Fontes macroeconômicas.
2. Nota semanal e baselines.
3. Hash e congelamento.

**CONFIRMADO POR ANÁLISE ESTÁTICA — D20 e escopo do piloto:**

W1 e M1 permanecem descritivos.

A expansão aos 28 pares Forex deverá esperar a etapa atual.

**INFERIDO:** Nenhuma prioridade documental autoriza iniciar uma etapa sem a aprovação exigida pelo protocolo.

## 5.5 Regras de integridade que permanecem

**CONFIRMADO POR ANÁLISE ESTÁTICA — D5, D9, D14, D15 e D30:**

- A versão confirmatória será congelada antes do início oficial.
- As previsões deverão ter integridade e anterioridade demonstradas.
- A avaliação principal utilizará 52 semanas prospectivas e informativas.
- O teste conjunto deverá vencer os três baselines.
- Não haverá parada antecipada baseada em resultado favorável.
- Um teste inconclusivo não será transformado em vitória.
- Uma mudança na versão oficial exigirá avaliação nova, conforme D15.

**NÃO VERIFICADO:** Nenhuma dessas condições foi demonstrada como integralmente implementada ou concluída.

---

# 6. LIMITAÇÕES E CONFERÊNCIA FINAL

## 6.1 Limitações

**NÃO VERIFICADO:** Este registro não demonstra desempenho preditivo, assertividade ou superioridade estatística do Motor A.

**NÃO VERIFICADO:** A captura macroeconômica, a latência das fontes, a publicação do hash, o deslocamento histórico UTC do MT5 e a integração de ponta a ponta ainda não foram validados neste documento.

**INFERIDO:** O fechamento documental do Estudo D23 não equivale à autorização operacional do piloto.

**CONFIRMADO POR ANÁLISE ESTÁTICA:** Os únicos limites explicitamente registrados como provisórios neste documento são o piso de cobertura de 50% e o recuo de cinco sessões. Nenhum deles foi convertido em valor definitivo.

**NÃO VERIFICADO:** As correções exatas adicionais do StatCan e da nota E6 exigem conferência do auditor, conforme as ressalvas expressas na seção 4.

## 6.2 Pedido de conferência ao auditor

**Solicitação:** Claude, confira integralmente este Registro Final Único contra as decisões da Consolidação Rev 8, do Adendo revisado, da Matriz Rev 5, da Tabela D23 revisada e das confirmações posteriores do proprietário, identificando divergências e textos não localizados, **sem modificar dados nem realizar ações externas**.

**Estado após a conferência:** Esta é a única revisão posterior ao parecer do auditor permitida pelo proprietário. Pendências documentais pequenas não devem ser tratadas automaticamente como impedimento de fechamento.

**NÃO VERIFICADO:** Nenhuma autorização para abrir PR foi fornecida nesta tarefa.

A PR documental permanece bloqueada até o proprietário escrever expressamente:

**"pode abrir a PR"**

---

# O QUE MUDOU — REGISTRO DE CORREÇÕES

## Correções documentais originalmente registradas

| Nº | Correção | Situação neste Registro Final |
|---|---|---|
| 1 | Título da seção 8 da Rev 8 | **CORRIGIDO NO TEXTO FINAL** — referência à Rev 8 em relação à Rev 7 |
| 2 | Expressão sobre ambiguidade da voz | **INFERIDO: D25, não D33.** Trechos literais da Rev 8: **NÃO LOCALIZADO — auditor confere** |
| 3 | Rótulo de ausência de execução no Adendo | **AINDA A APLICAR NO ARQUIVO FINAL** — seção 1.3 já corrigida, mas encerramento ainda contém a expressão antiga |
| 4 | Movimento exatamente zero, categoria 5 | **JÁ CORRIGIDO NO ADENDO, SEÇÃO 6.1** — trecho da categoria 5 confirmado |
| 5 | Matriz Rev 5 — item 78 e P4 | **JÁ REGISTRADO NO ADENDO, SEÇÕES 8.4 E 8.5; AINDA A APLICAR NO ARQUIVO FINAL DA MATRIZ** |
| 6 | BCE — página de visão geral | **CORRIGIDO NO TEXTO FINAL** — página aberta pelo auditor; disponibilidade de outros endpoints não presumida |
| 7 | StatCan — atribuição | **DISTINÇÃO DOCUMENTAL REGISTRADA** — texto exato adicional NÃO LOCALIZADO, auditor confere |
| 8 | Eurostat — referência E6 | **RESSALVA DOCUMENTAL REGISTRADA** — texto exato da nota NÃO LOCALIZADO, auditor confere |

## Seis alterações desta revisão única

| Item | Alteração solicitada pelo auditor | Resultado |
|---|---|---|
| **1** | Corrigir o rótulo de ausência de execução da seção 1.3 | **APLICADO:** "Sem execução nesta tarefa" |
| **2** | Retificar a referência D33/D25 e conferir os trechos da Rev 8 | **APLICADO COM RESSALVA:** D25 classificada como INFERIDO; texto literal da Rev 8 NÃO LOCALIZADO |
| **3** | Corrigir a origem da leitura das sessões no MT5 | **APLICADO:** leitura de tela atribuída ao proprietário e conferência documental ao auditor |
| **4** | Resolver individualmente as situações das correções 3, 4 e 5 | **APLICADO:** ocorrência remanescente identificada; categoria 5 confirmada; pendências da Matriz distinguidas |
| **5** | Indicar a origem da regra ESTÁVEL válida para cobertura | **APLICADO:** Adendo revisado, seção 4.1, com reprodução literal e rótulo INFERIDO |
| **6** | Acrescentar fontes específicas utilizadas nesta revisão | **APLICADO:** seção seguinte, uma referência por alteração |

---

# FONTES USADAS NESTA REVISÃO

**1. Correção do rótulo de execução:** Registro Final anterior, seção 1.3; Adendo revisado, seção 1.3 e encerramento.

**2. Ambiguidade de voz e D25:** Relato corretivo do proprietário nesta tarefa; Adendo revisado, seções 2.1 e 2.2. Texto literal da Rev 8, seção 8 item 3 e seção 9 item 4: **NÃO LOCALIZADO — auditor confere**.

**3. Origem da leitura das sessões:** Tabela D23 revisada, seção A; relato do proprietário que atribui a leitura da tela do MT5 a ele próprio e a conferência documental ao auditor.

**4. Correções 3, 4 e 5:** Adendo revisado, seções 1.3, 6.1, 8.4, 8.5 e encerramento; Matriz Rev 5, seção 11, item 78, e seção 11.2, P4.

**5. Regra ESTÁVEL para cobertura:** Adendo revisado, seção 4.1, parágrafo **INFERIDO — esclarecimento da cobertura**, reproduzido na seção 2.c deste documento.

**6. Registro das seis correções e rastreabilidade:** Registro Final Único anterior, seções 1.3, 2.c, 3 e 4 e tabela "O QUE MUDOU"; solicitações corretivas expressas pelo proprietário nesta tarefa.

---

**CONFIRMADO POR ANÁLISE ESTÁTICA — escopo desta revisão:** Foram incorporadas as seis alterações solicitadas, com preservação das demais decisões e regras do registro anterior.

**NÃO VERIFICADO:** Os trechos literais da Rev 8 identificados como não localizados continuam sujeitos à conferência do auditor. Nenhuma informação ausente foi reconstruída como citação documental.

**Sem execução nesta tarefa.** Não foram realizados acessos a sistemas externos, alterações em repositórios, cadastros, integrações ou abertura de PR.

**ESTADO FINAL: DOCUMENTO / LAB / AGUARDAR CONFERÊNCIA FINAL / HARD NO-GO.**