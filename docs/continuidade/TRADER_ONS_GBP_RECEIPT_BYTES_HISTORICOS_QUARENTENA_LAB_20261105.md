# AtlasQuant Trader — recibo de bytes de arquivos ONS/GBP (LAB)

**Data:** 05/11/2026. **Escopo:** prova interna de integridade do arquivo fornecido, sem coleta real.

Com as versões históricas `v131`, `v130`, `v129` e `v128` localizadas na página oficial do ONS, o próximo risco é confundir a posse de um arquivo com prova de que o dado estava disponível na hora da decisão do mercado.

## Entrega

`atlasquant_trader_ons_gbp_archived_payload_receipt_lab.py` recebe **bytes opacos**, ID da versão, URL, código e tipo HTTP informados pelo coletor, tamanho declarado, hash SHA-256 fornecido e instantes UTC da captura e do corte histórico. Ele não lê nem interpreta o conteúdo CSV; portanto, não certifica nenhuma taxa de inflação.

Regras de recusa explícita:

- Fora dos quatro IDs oficiais previamente identificados ou URL diferente do endereço exato fixado para aquele ID.
- Tamanho ausente, falso, diferente dos bytes ou acima do limite configurado (2 MiB).
- SHA-256 ausente, não hexadecimal estrito ou divergente dos bytes efetivamente fornecidos.
- Status HTTP diferente de `200`; tipo informado fora de `text/csv`, `application/csv` e `application/octet-stream` com parâmetros de charset restritos.
- Horário sem fuso, captura posterior à avaliação ou instante histórico posterior à avaliação.

Se a estrutura do recibo for internamente consistente, o estado será `LAB_ONS_ARCHIVE_BYTES_INTERNALLY_MATCHED_QUARANTINED`: **integridade da cópia recebida**, não autenticação independente. Mesmo nessa condição:

`publisher_tls_origin_verified=false`, `http_response_independently_observed=false`, `external_sha256_independently_attested=false`, `payload_csv_structure_verified=false`, `original_historical_snapshot_independently_verified=false`, `release_instant_independently_verified=false`, `point_in_time_historically_available_verified=false`, `usable_for_backtest=false`.

O recibo também registra apenas o enquadramento de calendário da versão por **data de substituição**, que não é a data de publicação original. A única prova obtida com comparação de hash é que os bytes entregues correspondem ao hash informado; isso não demonstra quando o arquivo foi publicado, se veio de fato do ONS, se houve redirecionamento ou se seus dados eram conhecidos no momento do trade.

## Próxima prova pendente

Com o AM12 online, obter a resposta original por HTTPS, registrar URL inicial/final, certificado TLS validado, cabeçalhos, status, horário local, SHA-256 e arquivo original. Comparar o formato real com o parser antes de permitir qualquer hipótese histórica. Atestação independente do instante de publicação, direitos de uso e consenso pré-evento continuarão pendentes.

**HARD NO-GO:** testes puramente sintéticos, nenhuma chamada externa, nenhum custo novo, nenhum merge, deploy, Worker ou ordem real. Continuidade na PR Draft #1815; interface #1816 não alterada.
