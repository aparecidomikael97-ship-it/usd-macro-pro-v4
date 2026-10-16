# A123 — Admissão e recibos sintéticos, laboratório offline

**Aviso P0: NÃO PRODUTIVO, NÃO EQUIVALE A CUSTÓDIA INDEPENDENTE.**

Este diretório contém `contract.py` (ToyVault SQLite + ToySigner HMAC + FakeSender), `test_contract.py` (38 casos), `A123_ADR_RECEIPTS_CRASH_CUTS.md` (matriz de cortes de falha), `A123_RED.log`, `A123_GREEN.log`. Uma falha sob co-rollback é intencionalmente mantida e o teste 35 **passa ao demonstrar a vulnerabilidade**.

Executar (Python 3.13/Linux):

```bash
cd labs/a123_receipts_offline
PYTHONWARNINGS=error::ResourceWarning python -m unittest -v test_contract
```

Sem SDK de nuvem ou APIs. Os dois bancos ficam no mesmo ambiente de teste, podem ser apagados/restaurados juntos. Signatário HMAC possui chave simulada dentro do processo. Não enviar este código à produção. Mantenha Worker OFF/HARD NO-GO. O projeto AION, Outbox/Saga, Core V1, `main`, provider e recursos externos não são alterados.
