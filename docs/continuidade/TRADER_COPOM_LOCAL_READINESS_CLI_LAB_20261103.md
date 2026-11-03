# AtlasQuant Trader — consulta local da prontidão do Copom (LAB 03/11/2026)

**Entregue:** `atlasquant_trader_copom_readiness_cli_lab.py`, um comando Python **somente de leitura** para usar pelo terminal/Codex, sem precisar mudar a interface aprovada. Ele utiliza o checkpoint PRÉ-Copom original, congelado no Git pelo commit `1281f21860211e9b6f784c649396aa56d17ecdf5`, e chama a checagem unificada `atlasquant_trader_copom_evidence_readiness_lab.py`.

## Como consultar

No diretório do repositório (ambiente Python 3.11+), exemplo PRE-EVENTO:

```bash
python atlasquant_trader_copom_readiness_cli_lab.py --as-of 2026-11-03T20:30:00Z
```

Para saída JSON padronizada, sem qualquer conexão externa:

```bash
python atlasquant_trader_copom_readiness_cli_lab.py --as-of 2026-11-03T20:30:00Z --format json
```

`--as-of` é **obrigatório e precisa estar em UTC com Z**, no formato `AAAA-MM-DDTHH:MM:SSZ`. **É um horário declarado pelo operador; não prova o momento real de execução ou disponibilidade da informação.** O CLI compara esse horário com o relógio local do computador (**também não atestado independentemente**) e **recusa datas futuras**, a menos que seja solicitada explicitamente uma simulação. No JSON permanecem `declared_clock_utc_unattested`, `wall_clock_independently_verified=false` e agora `local_machine_clock_independently_attested=false`. Um corte temporal anterior à pesquisa bloqueia a consulta. O CLI nunca atualiza o checkpoint original.

**Para preparar ou testar um cenário FUTURO, use modo explícito de simulação (sem notícia real):**

```bash
python atlasquant_trader_copom_readiness_cli_lab.py --as-of 2026-11-05T13:00:00Z --simulate-future --format json
```

Neste modo a saída fica marcada como `LAB_FUTURE_SIMULATION_ONLY`, `future_simulation_mode=true` e apresenta aviso de **SIMULAÇÃO DE DATA FUTURA** no texto. Se tiver CSV, só aceita manifesto `SYNTHETIC_FIXTURE` e `fixture_mode=true`. **Não é permitido simular uma data futura com um arquivo que alega conter cotações reais**; a checagem recusa o arquivo, sem gerar relatório enganoso. Isso continua sendo apenas uma proteção contra uso acidental; um relógio local manipulado não é prova externa de tempo.

**Opcional para estudo FUTURO com arquivo local obtido por meio autorizado:**

```bash
python atlasquant_trader_copom_readiness_cli_lab.py --as-of 2026-11-05T13:00:00Z --csv arquivo-local.csv --manifest origem-local.json --format json
```

**O exemplo com arquivo declarado real somente poderá ser executado quando o relógio do computador já indicar a data/hora informada ou posterior.** Não use `--simulate-future` para esse caso; o modo de simulação o recusará. O exemplo após o evento indica apenas formato/fluxo de leitura: não presume que exista arquivo real, sessão efetiva em 05/11 ou que a decisão do Copom tenha sido divulgada. **Não use os exemplos para fingir histórico.** CSV e manifesto devem ser fornecidos em par. O CLI não baixa nem salva dados; lê, no máximo, **4.000 bytes CSV** e **4.096 bytes do manifesto**, exige UTF-8 e recusa chaves duplicadas no JSON. A checagem dos horários, vencimentos, identificadores e SHA dos preços segue no importador offline já testado.

A informação de autorização/licença de uma exportação declarada continua **NÃO VERIFICADA**, e deve ser examinada fora do CLI. A página de boletins da B3 veda coleta automatizada, inclusive IA; este comando **não coleta** nenhuma página, cotação ou endpoint. A integridade local do CSV não confirma quem o criou.

## O que o resultado significa

- **Checkpoint original:** integridade de bytes Git observada; não é selo independente de horário.
- **Resultado do Copom:** `NO_AUTHENTICATED_RESULT` até registro oficial confirmado.
- **B3:** apenas horários regulares documentais, não ticks reais ou autorização de dados.
- **Cotações:** `NO_AUTHENTICATED_PRICE_DATA` sem exportação; arquivos declarados continuam candidatos.
- **Direção:** sempre **AGUARDAR**; sem taxa de acerto calculada, recomendação, autorização de trade ou feed ao Radar.
- **Pendências:** sete provas independentes explicitamente relacionadas à origem, tempo, licença, negociação, cenário macro e avaliação pré-registrada.

A saída textual em português é um **resumo de status do laboratório**, não um painel em produção. A saída JSON destina-se a validações offline futuras, sem conter os preços brutos fornecidos por terceiros.

## Testes e proteção

`test_atlasquant_trader_copom_readiness_cli_lab.py`: **20 cenários sintéticos**, incluindo leitura exata do checkpoint, resumo em português, JSON, horários UTC recusados, CSV/manifesto incompletos, arquivos ausentes, duplicatas de chave, conteúdo adulterado, arquivos grandes, dados de preço futuro, não vazamento de preços brutos no resumo e direitos de uso não verificados.

A entrada foi integrada ao Quality CI, sujeito à aprovação do novo commit. **LAB / HARD NO-GO, sem custo novo, Render, Worker, scheduler, scraping, rede, merge, deploy, ordens ou alteração de UI.**
