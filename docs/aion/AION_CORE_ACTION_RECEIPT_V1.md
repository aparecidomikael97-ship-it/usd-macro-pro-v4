# AION Core Action Receipt V1

Data: 2026-09-29
Base: `cursor/aion-core-independence-v1` @ `6fa53fffacdfa17bbd26400f7d858ff3ccb961a2`

O envelope em `atlasquant_aion_action_receipt.py` aponta para receipts existentes por `receipt_id` e fingerprint. Não reimplementa o receipt de `atlasquant_aion_background_executor.py`.

O SHA-256 é fingerprint canônico. Não é assinatura.

Sem verifier, evidência, aprovação e policy ficam `MISSING` ou `UNVERIFIED`. Guardian ausente ou não booleano fica `UNKNOWN`. O envelope não executa ação.

Resultados com padrão de segredo são gravados já redigidos. O valor original não entra no envelope.
