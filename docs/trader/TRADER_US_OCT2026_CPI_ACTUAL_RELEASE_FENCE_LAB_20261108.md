# AtlasQuant Trader — controle do resultado real do CPI americano (LAB)

**Estado em 08/11/2026:** o CPI-U cheio **mensal com ajuste sazonal**
referente a outubro/2026 ainda **não foi divulgado**. A página oficial do BLS
agenda a publicação para **10/11/2026, 08h30 Eastern Time**
([calendário de novembro](https://www.bls.gov/schedule/2026/11_sched_list.htm),
[calendário do CPI](https://www.bls.gov/schedule/news_release/cpi.htm)).
Isso equivale a 13h30 UTC em novembro.

O novo `atlasquant_trader_us_cpi_actual_receipt_lab.py` prepara uma **porta de
recepção somente em memória, sem acesso à internet**, para quando houver
um documento candidato do resultado de outubro. Ele não inventa o valor
real do evento nem agenda downloads automáticos.

## Separação do que é conhecido

| Parte | Regra atual |
| --- | --- |
| Valor anterior de setembro | Documentado em pesquisa, mas sua origem P-I-T/captura independente ainda exige prova. |
| Consenso de outubro | Precisa ter sido capturado **antes de 10/11 13h30 UTC**, para o indicador e unidade exatos. Fonte, pesquisa e disponibilidade ainda não estão atestadas independentemente. |
| Resultado real de outubro | Só pode existir como candidato **após** a divulgação; sem captura, estado `LAB_WAIT_OFFICIAL_CPI_ACTUAL_DOCUMENT`. |
| Comparação real − consenso | Continua `None` até atestar separadamente o número e o consenso, mesmo quando bytes de exemplo têm hash válido. |
| Reação do EUR/USD, USD/JPY ou US500 | Nunca é deduzida apenas de um CPI acima/abaixo do consenso. |

O candidato de resultado usa uma URL BLS de CPI, código HTTP 200, HTML,
referência mensal `2026-10`, menção textual a outubro/2026 e ao CPI,
métrica
`CPI_U_HEADLINE_MOM_SEASONALLY_ADJUSTED_PERCENT_CHANGE`, horário com fuso,
SHA-256 do corpo e duração limitada da captura. Um caminho de arquivo futuro
de arquivo histórico do BLS é **apenas esperado**, não comprovadamente
existente em 08/11. O conteúdo numérico permanece uma **alegação não
autenticada**: este laboratório ainda não extrai nem confirma o valor na
tabela oficial.

Mesmo com corpo e hash idênticos, o módulo mantém:

```text
official_actual_verified = None
actual_minus_pre_release_consensus = None
market_reaction_probability = None
fx_bias = None
index_bias = None
operational_bias = AGUARDAR
live_alert_allowed = False
trade_authorized = False
publishable = False
```

Hash local **não é prova de emissor**, horário de publicação, licença,
metodologia da pesquisa de analistas ou disponibilidade histórica do texto.
Não há captura real nesta etapa. Nenhum HTML, arquivo de preço, dado de conta,
senha ou licença foi enviado ao repositório.

## Testes

`test_atlasquant_trader_us_cpi_actual_receipt_lab.py`: **17/17 testes
sintéticos aprovados**. Foram simulados antes/depois do anúncio, ausência
de resultado, arquivo alterado, relógio futuro, CPI YoY incorreto, fonte
de setembro reutilizada, HTML de setembro renomeado como outubro, HTTP
inadequado, consenso tardio e número falso.

Com os módulos previamente selecionados da pesquisa de CPI, eventos G8,
matriz macro e filtros de preço/viés, a execução de 08/11 terminou com
**197 testes coletados: 196 aprovados, 1 pulado** (dependência dos arquivos
reais do MT5 não disponíveis neste executor). A regressão selecionada não
equivale à suíte completa nem a uma auditoria de fontes oficiais.

O trabalho fica na PR em modo DRAFT. Não foi adicionada tarefa agendada,
assinatura, cobrança, uso de MT5, integração ao aplicativo, ordem de
compra/venda ou execução automática.
