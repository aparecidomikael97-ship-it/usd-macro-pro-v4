# AtlasQuant Trader — Eurostat CPI, leitura documental em LAB (09/11/2026, Cuiabá)

## Escopo

Após a captura oficial Eurostat feita no AM12 e a verificação de SHA-256 no
arquivo local, acrescentamos um leitor **somente de leitura** para avaliar a
coerência de três referências presentes no **mesmo HTML**:

1. Etiqueta da publicação: `Flash estimate - October 2026`;
2. Manchete: `Euro area annual inflation up to 4.0%`;
3. Descrição OG e linha `All-items HICP` da tabela, distinguindo taxa anual
   do último campo, que é a variação **mensal**.

O parser exige período, etapa FLASH, colunas anuais esperadas, valor numérico
e concordância. Captura a alegação de data `article:published_time`, mas **não
confunde** esse campo editorial com carimbo de primeira divulgação atestado.
Não calcula viés, não acessa MT5, não consulta preço, não faz HTTP e não cria
arquivos novos. Em qualquer divergência, devolve bloqueio e `AGUARDAR`.

O caminho de arquivo aceito na verificação é restrito ao manifesto EUR FLASH
2026-10 da publicação oficial `2-04112026-ap`; o verificador anterior reabre
os bytes, compara comprimento e SHA-256 e rejeita corrupção. A confirmação
de conteúdo entre partes **de uma única página** não constitui comprovação
independente do dado econômico.

## Validação registrada

- Testes locais isolados do novo leitor: **11/11 OK**.
- Conjunto `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **152/152 OK**.
- Casos adversariais: diferença manchete/OG/tabela, valor sem marca `e`,
  mês ou etapa errados, cabeçalho de tabela manipulado, duplicidade,
  metadados temporais inválidos, HTML não UTF-8, corpo adulterado,
  manifesto de outra origem e conferência de nenhuma escrita.
- **Executado no HTML real do AM12:** após corrigir uma transferência parcial,
  o arquivo Python remoto ficou com **9.716 bytes** e SHA-256
  `d21ef82e44d591752eac2b9fd5c477ba0a8437c0bff0d4676f480f4599ec7a14`,
  idêntico ao código testado no ambiente de desenvolvimento.
- O leitor foi executado pelo Python do AM12 sobre o manifesto
  `EUR_CPI_FLASH_2026-10_20261110T011636Z_7013d492f8af.manifest.json`
  e retornou `LAB_EUR_CPI_FLASH_DOCUMENTARY_EXTRACTED_UNATTESTED` com
  `local_archive_integrity_verified=true`,
  `same_document_value_consistent=true`, `documentary_cpi_yoy_percent=4.0`,
  `documentary_previous_yoy_percent=3.8`, `reference_period=2026-10`,
  `publication_stage=FLASH` e `file_writes=0`.
- O HTML declara `article:published_time=2026-11-04T10:00:00Z`;
  **esse horário é alegação editorial da própria página, não atestação de
  primeira divulgação**. Não usar para reconstruir viés antes da captura.
- A leitura real não cria novos arquivos, não atualiza conta MT5 e mantém
  `can_feed_macro_bias=false`, `historical_point_in_time_eligible=false`,
  `value_independently_verified=false`, `trade_authorized=false` e
  `operational_bias=AGUARDAR`.

## Limites explícitos

- O arquivo anterior AM12 continua preservado; não subir HTML bruto ao PR.
- `4.0%` é um resultado **documental atribuído à página**, não evidência de
  previsão correta, snapshot de vintage P-I-T, acerto de direção ou gatilho
  de compra/venda.
- `issuer_first_release_authenticated=False` e
  `historical_point_in_time_eligible=False` permanecem invariáveis.
- Sem alteração de produção, main, merge, publicação, Render, jobs, cobrança
  ou ordens no Pepperstone/MT5.

## Próxima trava

Próximo trabalho: desenhar um contrato de observações macroeconômicas
**bilaterais** com tempo de disponibilidade atestado por moeda e revisão,
antes de qualquer ligação ao score de probabilidade ou viés. Para outras
moedas, usar leitores específicos por emissor; não replicar o formato da
página Eurostat como se fosse universal. Sem inventar vintage ou viés.
