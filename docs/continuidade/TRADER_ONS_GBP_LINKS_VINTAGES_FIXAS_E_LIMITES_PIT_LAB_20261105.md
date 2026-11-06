# AtlasQuant Trader — identificadores de arquivos históricos ONS/GBP (LAB)

**Data da pesquisa:** 05/11/2026. **Situação:** catálogo auditável de links, sem bytes originais e sem prova de disponibilidade intradiária.

Fonte primária oficial: https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous

O ONS lista arquivos anteriores da série `D7G7`, base `MM23`, com as datas em que **deixaram de ser a versão vigente** (*Date superseded*). A investigação dos links oficiais de download identificou os seguintes caminhos, todos com `format=csv` no gerador do domínio `www.ons.gov.uk`:

| ID confirmado no link oficial | Data de substituição exibida | Conteúdo original arquivado? |
| --- | --- | --- |
| `v131` | 21/10/2026 | Não |
| `v130` | 16/09/2026 | Não |
| `v129` | 19/08/2026 | Não |
| `v128` | 22/07/2026 | Não |

O módulo `atlasquant_trader_ons_gbp_archived_link_catalog_lab.py` fixa os quatro endereços do gerador de arquivos históricos com as respectivas datas de substituição. Aceita opcionalmente um ID exato, um instante histórico de corte e o instante UTC de avaliação. Rejeita IDs não registrados, datas sem fuso e corte posterior ao horário de avaliação.

### Regra de cronologia sem antecipação

- **Corte anterior à data de substituição:** apenas limite superior; **não prova que essa versão já existia** naquela data. Uma versão substituída em outubro pode nem ter sido publicada em julho.
- **Corte no mesmo dia da substituição:** indisponibilidade de hora exata, bloqueio intradiário.
- **Corte posterior à substituição:** versão sabidamente não vigente pela data de calendário, embora possa continuar acessível como arquivo.

Esses estados **não selecionam automaticamente a vintage correta** para backtests. Não são uma confirmação de qual valor era conhecido na hora da decisão. O catálogo não consulta a rede, não faz download, não interpreta os conteúdos CSV e não atribui carimbo histórico de publicação a qualquer arquivo.

O leitor JSON exploratório e o detector de diferenças entre dois JSONs sintéticos continuam **separados** deste catálogo de downloads CSV reais: ainda é preciso conferir o formato dos arquivos originais antes de uni-los. SHA-256, quando obtido, comprova integridade dos próprios bytes, não a identidade do servidor ou a publicação *ex ante*.

**Próxima ação no AM12 online:** obter arquivos pequenos dos links oficiais para testar estrutura, preservar o corpo original e o cabeçalho de resposta, hora UTC local, URL final, hash, direitos de uso e a cadeia de custódia. Os downloads devem permanecer LAB e separados de sinais operacionais.

**HARD NO-GO:** `historical_point_in_time_available_verified=false`, sem Ranking, Radar, Worker, publicação, merge, operações reais ou assinatura paga. Continuidade na Draft PR #1815, sem alterar a PR #1816.
