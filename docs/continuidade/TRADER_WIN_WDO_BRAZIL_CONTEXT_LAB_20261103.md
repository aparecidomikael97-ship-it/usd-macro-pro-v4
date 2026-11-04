# Trader — fundamentos oficiais do Brasil para WIN/WDO (LAB 03/11/2026)

## Intenção
O proprietário prioriza antecipar o **viés macro** diário, semanal e mensal, não FVG/OB. Este módulo acrescenta **informações domésticas do Brasil** ao calendário macro dos EUA já presente no Trader. A fonte externa USD **não** substitui Selic, IPCA, trabalho e atividade do Brasil.

Código: atlasquant_trader_win_wdo_brazil_context_lab.py
Testes: test_atlasquant_trader_win_wdo_brazil_context_lab.py

## Leitura oficial disponível antes da reunião de novembro
| Fato observado | Valor documental | Referência | Publicado | Fonte primária |
|---|---:|---|---|---|
| Meta Selic, decisão anterior | **13,75% a.a.** | Vigência 17/09 | 16/09/2026 | [Comunicado BCB 45.963](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=45963&tipo=Comunicado) |
| IPCA cheio, mês | **0,82%** | Setembro | 09/10/2026 | [IBGE – IPCA](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html) |
| IPCA cheio, 12 meses | **4,58%** | Setembro | 09/10/2026 | [IBGE – IPCA](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html) |
| PNAD desocupação | **5,2%** | Trimestre móvel jul–set | 30/10/2026 | [IBGE – PNAD Contínua](https://www.ibge.gov.br/estatisticas/sociais/trabalho/2511-np-pnadcontinua/17270-pnad-continua.html) |
| PIB real, com ajuste sazonal | **+0,5%** | 2º tri contra 1º tri | 01/09/2026 | [IBGE – Contas Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/servicos/9300-contas-nacionais-trimestrais.html?lang=pt-BR) |
| PIB real, interanual | **+2,0%** | 2º tri contra 2º tri de 2025 | 01/09/2026 | [IBGE – Contas Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/servicos/9300-contas-nacionais-trimestrais.html?lang=pt-BR) |

**Não misturar metodologias:** IPCA mensal não é IPCA em 12 meses; PNAD divulgada mensalmente mede **trimestre móvel**, não um mês isolado; PIB trimestre contra trimestre não equivale ao interanual, e a taxa em quatro trimestres (1,9%) é diferente da alta interanual de 2,0%.

## Catalisadores futuros identificados na fonte oficial
- **Copom 03–04/11**: a reunião termina com decisão em **04/11**. O [comunicado BCB de setembro](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=45963&tipo=Comunicado) confirma próxima reunião em 03–04/11. O LAB utiliza intervalo de **dia inteiro em UTC** para não afirmar um horário de publicação/captura não assinado.
- **IPCA de outubro: 12/11**, de acordo com o [calendário IBGE](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-ipca.html). **Não** usar o IPCA de outubro antes da divulgação; o valor existente é de setembro.
- **IBC-Br de setembro: 16/11**, conforme o [calendário BCB](https://www.bcb.gov.br/estatisticas/calendario_indicadores). Este módulo registra **somente a agenda futura**, sem inventar valor de IBC-Br/consenso.

**Frente a 03/11 às 12h UTC**, os próximos 24h cortam o meio do dia UTC 04/11: o evento Copom recebe WINDOW_EDGE_TIME_UNCERTAIN, **não uma certeza de hora**. Em W1 ele está integralmente na janela; em MN1 também aparecem IPCA/IBC-Br. As janelas são 24h/7d/30d rolantes, não candles ou previsões.

## Vínculo WIN vs WDO
- **WIN**: fatos e eventos do Brasil mais impactos externos USD, *por canais distintos*. Sensibilidade aos juros, lucro, fiscal e fluxo local ainda não calibrada.
- **WDO**: fatos e eventos do Brasil, com calendário USD do módulo anterior. O real/dólar depende de expectativas **relativas** de juros Brasil/EUA, dólar global, risco, fluxo e geopolítica — nenhuma direção automática por "Selic alta".
- Os **6 registros** domésticos são transcrições documentais manuais. Páginas de resultado IBGE podem ser atualizadas, portanto **não representam recibos históricos assinados nem hash de captura independente**. A consulta só é autorizada como leitura LAB a partir de 03/11.
- **Copom em 04/11**: a meta Selic anterior (13,75%) permanece identificada como **decisão anterior exigindo verificação**, jamais rotulada como nova decisão automaticamente.
- **IPCA em 12/11**: o dado anterior permanece histórico e fica com marcador de revisão. Não adquirir a leitura futura por retrocesso temporal.

A saída tem **2 índices x 3 horizontes = 6 linhas**, com documentos, agenda brasileira e exposição USD separados; pre_event_consensus e probability_calibrated ficam nulos, directional_bias fica AGUARDAR, trade_authorized fica false.

## O que falta antes do viés antecipatório
1. Pesquisa **Focus** na edição correta disponível **antes** da decisão, com expectativas Selic/IPCA e campo de data de coleta; curva de DI de mercado com custódia e licença apropriadas.
2. Surpresas ante consenso publicado antes de cada release, fiscal/fluxo cambial, preços independentes de WIN/WDO e micro/geopolítica.
3. Tese ex-ante D1/W1/MN1 e sua invalidação; validação fora da amostra, custos/abstenção, baseline e métricas calibradas antes de qualquer "90%".

**LAB / HARD NO-GO.** PR DRAFT; sem Worker, scheduler, produção, ordens, custos, deploy, merge ou mudança no visual aprovado.
