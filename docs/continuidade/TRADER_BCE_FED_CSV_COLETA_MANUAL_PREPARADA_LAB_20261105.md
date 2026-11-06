# AtlasQuant Trader — coleta manual dos níveis de juros BCE/Fed (LAB)

> Este é o checkpoint **anterior à captura real**. A consulta foi realizada
> posteriormente no AM12 para ambas as fontes. A série BCE retornou níveis
> **diários**, não apenas datas de mudança. Ver
> `TRADER_EURUSD_JUROS_CAPTURAS_REAIS_AM12_LAB_20261105.md`.

Continuação técnica de 05/11/2026, branch da PR #1815 (DRAFT). Nenhuma
alteração em `main`, PR #1816, produção, AION Worker ou integrações de ordens.

## Estado honesto

**Coletor implementado e testado somente com respostas simuladas.** A rede
deste ambiente não conseguiu estabelecer conexão com o endpoint de dados do
BCE (timeout de proxy). Isso não comprova indisponibilidade do BCE. Nenhum
CSV real de política monetária foi capturado nesta etapa; a adequação da
estrutura CSV às respostas atuais ainda precisa ser comprovada no AM12.

As fontes são:

- [BCE: série FM.D.U2.EUR.4F.KR.DFR.LEV](https://data.ecb.europa.eu/data/datasets/FM/FM.D.U2.EUR.4F.KR.DFR.LEV): **taxa de depósito observada diariamente**; uma linha não prova nova decisão, anúncio ou mudança de nível.
- [FRED: DFEDTARL](https://fred.stlouisfed.org/series/DFEDTARL) e [DFEDTARU](https://fred.stlouisfed.org/series/DFEDTARU): limites da faixa-alvo dos Fed Funds **vigentes por dia**, não consenso pré-FOMC. A fonte original é o Federal Reserve Board; FRED é operado pelo Fed de St. Louis.

Os dois endpoints candidatos estão fixos no código, não podem ser substituídos
por URL fornecida pelo chamador. A API formal do FRED exige chave e não foi
usada; o endereço usado aqui é uma **exportação CSV do gráfico**, sujeita a
validação de estabilidade, resposta, direitos e condições de uso antes de
qualquer integração operacional.

## Protocolo de uma única requisição manual

O arquivo `atlasquant_trader_eurusd_policy_capture_once_lab.py`:

1. Requer `--confirm-manual-http`, um dos dois IDs fixos e pasta de evidências
   já existente. Sem isso, zero requisições e estado bloqueado.
2. Exige HTTPS com validação de certificados pelo sistema, não aceita
   redirecionamento, limita a 1–15 segundos e 512 KiB por requisição.
3. Valida o tipo de conteúdo e interpreta somente a série esperada;
   duplicidades, valores inválidos ou dados ausentes são bloqueados.
4. Grava exclusivamente um ZIP novo em modo exclusivo, com `response.csv`
   original e `observation_receipt.json`; reabre ambos e verifica os bytes.
5. Distingue duas situações: parser aceito (ainda QUARENTENA) ou parser
   recusado (bytes arquivados para diagnóstico, SEM valor confiável).

Exemplo para PowerShell **no AM12, após conferir que a pasta existe**:

```powershell
python .\atlasquant_trader_eurusd_policy_capture_once_lab.py --source ECB_EUR_DFR_EFFECTIVE --archive-dir "C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence" --confirm-manual-http
```

Depois, separadamente, se a exportação FRED for acessível sem login ou
contratação e seu uso for permitido:

```powershell
python .\atlasquant_trader_eurusd_policy_capture_once_lab.py --source FED_USD_TARGET_RANGE_EFFECTIVE --archive-dir "C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104\evidence" --confirm-manual-http
```

**Não executar os comandos sem confirmar que o AM12 está na revisão certa,
que a pasta existe e que a consulta manual isolada está autorizada.** Se vier
403, redirect, alteração de formato ou timeout, registrar recusa. Não procurar
rota alternativa, não inserir senha ou contratar chave paga automaticamente.

Os hashes SHA-256 confirmam integridade dos bytes que o computador recebeu;
não são assinatura institucional. O relógio local e cabeçalhos HTTP são
metadados, **não prova independente de horário de publicação**. Sem consenso
pré-decisão, comunicado primário datado, histórico point-in-time, direitos
de reutilização, preço FX independente nem validação OOS, a comparação de
juros não produz um viés.

Estado permanente nesta fase: `operational_bias=AGUARDAR`,
`trade_authorized=false`, `can_feed_live_radar=false`.

## Verificações

```bash
python -m unittest -q test_atlasquant_trader_eurusd_policy_capture_once_lab.py test_atlasquant_trader_eurusd_policy_levels_lab.py
python -m py_compile atlasquant_trader_eurusd_policy_capture_once_lab.py
```

Testes com transporte falso incluem ausência de opt-in, HTTP diferente de 200,
redirecionamento, conteúdo não CSV, codificação inesperada, payload excessivo,
arquivo inexistente, arquivamento e leitura de volta do ZIP, SHA, taxa válida,
valores inválidos, ausências e proibição de liberação ao Radar.
