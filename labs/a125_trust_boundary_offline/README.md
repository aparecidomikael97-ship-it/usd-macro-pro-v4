# A125 — interface de confiança e exclusividade de envio, SOMENTE OFFLINE

Material educacional/auditável do AtlasQuant AION. **NÃO DEPLOY / NÃO HOMOLOGADO**. Não altera Outbox, Saga, AION produtivo ou Worker. Sem rede, contas, banco real, fornecedor ou chaves verdadeiras. Nada aqui pode certificar F1/T1/H0/F2.

## Executar com Python 3.13, stdlib

```bash
cd labs/a125_trust_boundary_offline
python -W error -m unittest -v test_contract.py  # 29/29; 4 PASS = exploits ABERTOS
python -W error -m unittest -v red_baseline.py   # 1 FAIL esperado; pós-verificação tarde demais
```

No pacote ZIP também estão cópias imutadas dos laboratórios anteriores para executar regressão separada (A124 31/31, A123 38/38). O ZIP é uma cópia informativa, não uma integração real.

**Resultados:** 25 verificações condicionais, 4 vulnerabilidades demonstradas na A125, 1 baseline propositalmente vermelho; 32 threads concorrentes, não hosts/processos. Leia `A125_INTEGRATION_CONTRACT_AND_EXIT_GATES.md` para os 12 gates ainda abertos.
