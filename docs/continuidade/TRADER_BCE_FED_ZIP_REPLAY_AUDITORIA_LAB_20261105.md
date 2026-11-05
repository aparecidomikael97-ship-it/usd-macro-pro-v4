# AtlasQuant Trader — reabertura independente de evidências BCE/Fed (LAB)

Checkpoint 05/11/2026, PR #1815 DRAFT. Complementa o coletor manual
`atlasquant_trader_eurusd_policy_capture_once_lab.py` e os parsers offline
de níveis vigentes; **não é captura real nem liberação de trading**.

## O que o novo verificador faz

`atlasquant_trader_eurusd_policy_archive_verify_lab.py` recebe o caminho do
ZIP gerado pelo coletor e um **SHA-256 do arquivo completo registrado fora do
próprio ZIP**. Não executa HTTP, não escreve, não chama brokers e não precisa
de chave de API nem de serviço contratado.

1. Confere SHA-256 externo e tamanho máximo de 1 MiB.
2. Exige exclusivamente `response.csv` e `observation_receipt.json`, sem
   membros comprimidos, duplicados, criptografados ou caminho inesperado.
3. Reconfere hash dos bytes CSV, tamanho, fonte allowlisted, URL exata,
   horário UTC informado, flags de bloqueio e resultado declarado.
4. Reexecuta o parser da série BCE ou Fed sobre os **bytes originais** no
   horário indicado no recibo e exige resultado idêntico ao arquivado.
5. Mantém em quarentena tanto a captura com parser aceito como aquela em que
   o formato foi recusado; o campo `parser_accepted` distingue as duas.

O estado de sucesso técnico se chama
`LAB_ARCHIVE_INTERNAL_INTEGRITY_REPLAYED_QUARANTINED`. **A palavra
integridade significa somente consistência interna.** Uma pessoa poderia
forjar um arquivo e também um novo hash. Mesmo um SHA guardado em local
separado não prova origem institucional, instante do comunicado, revisão de
histórico, consenso pré-decisão, autenticidade de mercado ou lucro futuro.

## Como reabrir depois de uma captura real no AM12

O coletor imprime `raw_snapshot_archive_path` e
`raw_snapshot_archive_sha256`. Registre esses dados separadamente antes
de executar a verificação; substitua o exemplo abaixo pelos valores exatos:

```powershell
python .\atlasquant_trader_eurusd_policy_archive_verify_lab.py --archive "C:\CAMINHO\evidence\arquivo.zip" --expected-sha256 "INSIRA_SHA256_DE_64_CARACTERES"
```

O comando é **100% offline** e não altera o ZIP. Se houver divergência,
retorna código 2 e estado `LAB_ARCHIVE_VERIFY_BLOCKED`. Não consertar dados
desconhecidos por interpolação, não editar recibo e não transformar falha em
aceitação parcial.

## Verificações offline

```bash
python -m unittest -q test_atlasquant_trader_eurusd_policy_archive_verify_lab.py
```

Onze testes diretos cobrem sucesso de replay ECB/Fed, arquivo adulterado com
hash anterior, CSV e recibo adulterados com novo hash, sinal operacional
falsificado, URL/identidade alterada, relógio futuro, extração indevida,
compressão inesperada, arquivo grande e CLI read-only.

As séries seguem **instrumentos diferentes**: facilidade de depósito BCE
versus faixa-alvo do Fed. Próximo gate: coletar respostas reais, comparar
formatos, anexar comunicados oficiais e timestamps independentes, obter
expectativas anteriores e preços Forex independentes para backtest OOS.

Até lá, `operational_bias=AGUARDAR`, `trade_authorized=false`,
`can_feed_live_radar=false` e **HARD NO-GO** para operação real.
