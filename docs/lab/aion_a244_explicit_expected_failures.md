# A244 — Três contraprovas A243 passam a XFAIL explícito

Estado: **HARD NO-GO · P0 0/6 · sem autorização de operação**. Apenas teste e documentação de laboratório.

## Problema de comunicação corrigido

Na A243, os testes 14–16 contavam como PASS justamente quando reproduziam vulnerabilidades: (14) reserva duplicada após rollback de host+witness, (15) falsa raiz aceita após repinagem controlada pelo próprio host, (16) evento legítimo distinto bloqueado por digest semântico ambíguo. Uma bateria totalmente verde não distinguia a descoberta dessas violações de uma garantia cumprida.

## Mudança

- `labs/test_a243_signed_first_attempt.py`: os testes 14–16 usam `unittest.expectedFailure` e agora afirmam **o comportamento seguro desejado**, que a implementação atual não entrega.
- Espera-se o relatório `Ran 1166 tests ... OK (expected failures=3)`, com SKIP variável por sistema; confirmar no CI. A quantidade de testes não cresce.
- Se uma falha conhecida for corrigida, o teste vira `unexpected success` e **faz a suíte falhar** até que um revisor remova conscientemente o marcador XFAIL.
- Verde de CI significa que testes LAB rodaram conforme esperado; não atesta custódia externa, raiz independente nem segurança para executar efeitos reais.

## Para sair do XFAIL

14. Provar monotonicidade contra rollback em testemunha **externa à autoridade do host**, com teste real de reinicialização e recuperação.
15. Estabelecer fora do processo requisitante a identidade autêntica e a cadeia de custódia das chaves, sem repinagem arbitrária.
16. Obter identidade de evento de negócio imutável, atestada por origem independente, preservando eventos legítimos distintos e deduplicando reenvios equivalentes.

Somente após evidência independente revisada, atualizar implementação e retirar os XFAIL individualmente. Um campo textual `verified`, novo hash local ou outra fonte simulada nunca constitui prova.

**Sem Worker, merge, deploy, cobrança, provedor real, HUMAN_OWNER ou alteração de `UNCERTAIN=ZERO_AUTO_RESEND`.**
