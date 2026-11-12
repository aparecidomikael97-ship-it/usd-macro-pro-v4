# AtlasQuant Trader — vínculo do hash CPI com bytes de captura local (LAB)

Data de referência: 09/11/2026 (America/Cuiaba). Novo componente offline, não integrado a qualquer feed, worker, conta ou ordem.

## Falha tratada

A linha macro da matriz G8 continha `source_sha256`, que era apenas um hash **declarado pelo chamador**. Não havia um contrato que exigisse ter em mãos os bytes de um documento para verificar se o hash dessa linha batia com o conteúdo supostamente capturado. Assim, um erro de associação entre arquivo/país/período/estágio podia passar despercebido na pesquisa local.

## Implementação

Novo módulo `atlasquant_trader_g8_cpi_capture_binding_lab.py`, sem bibliotecas externas nem operações de rede:

1. `build_local_g8_cpi_capture_receipt_lab`: recebe bytes **fornecidos pelo chamador**, moeda, mês/trimestre, `FLASH` ou `FINAL`, URL HTTPS declarada e instante de captura; produz um recibo com base64, SHA-256 do corpo e SHA-256 autoconsistente do recibo. O status HTTP 200 e os metadados do emissor **não** são obtidos por rede: permanecem alegações.
2. `inspect_local_g8_cpi_capture_binding_lab`: verifica bytes, tamanho máximo de 1 MiB, SHA-256, esquema estrito, país, etapa, período, URL, horário de captura **igual** ao da linha macro e publicação/captura **não posteriores** à decisão. A referência monetária segue frequência NZD trimestral versus demais G8 mensal no recorte LAB 2026.
3. Se `macro_row.source_sha256 != receipt.body_sha256`, rejeita com `CPI_MACRO_SOURCE_HASH_NOT_BOUND_TO_CAPTURE_BYTES` (antes de qualquer uso informativo).

### Resultado válido não é certificação de divulgação

Estado retornado: `LAB_CPI_LOCAL_BYTE_HASH_BOUND_UNATTESTED`.

Isso significa exclusivamente **“estes bytes locais são autoconsistentes e seu hash coincide com o da linha macro”**. Alguém pode fabricar um documento e calcular corretamente todos os hashes. Este módulo:

- **não** baixa o site oficial, executa TLS, prova o servidor original ou lê cabeçalhos HTTP;
- **não** comprova a hora da primeira publicação, nem preserva logs de um relógio independente;
- **não** extrai ou valida a inflação numérica dentro do HTML/PDF;
- **não** fornece cobertura final, surpresa econômica, score, probabilidade, viés D1/W1/MN1 ou sinal MT5.

Todos os indicadores `issuer_tls_connection_verified`, `original_issuer_bytes_authenticated`, `first_publication_time_independently_attested`, `capture_clock_independently_attested`, `cpi_value_extracted_and_verified_from_body`, `historical_point_in_time_eligible` e `can_feed_macro_bias` permanecem `False` inclusive após vinculação de bytes. `operational_bias=AGUARDAR` e `trade_authorized=False`.

## Testes

- **9/9 PASS** na nova suíte, exclusivamente com bytes sintéticos: 8 moedas, flash, hash divergente, adulteração de corpo/relógio, URL de outro país, revisão, valor inválido, cronologia, limite de tamanho e corpo inteiramente inventado mas autoconsistente.
- Com as quatro suítes G8 anteriores: **115/115 testes locais PASS**.
- Não houve nova sessão AM12/MT5, coleta externa, arquivos de preço, merge, deploy, scheduler, worker, compra de serviço ou operação financeira.

## Próximo P0

Conectar uma captura real e auditável à URL **exata da divulgação** oficial com URL final/redirecionamento, certificado e status observados, carimbo independente de coleta e validação semântica do indicador/mês/valor. Só depois ligar esse recibo à matriz D1/W1 sob a política de as-of. Até lá, este módulo é prova de **integridade local**, não de *proveniência original*.
