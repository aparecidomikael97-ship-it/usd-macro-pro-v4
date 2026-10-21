# AION / AtlasQuant — Quality canônica: 85 FAIL/ERROR sem waiver

**Data:** 21/10/2026 | **Estado:** HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, 0/6 P0 homologados

## Por que este registro existe

As PRs Draft empilhadas #1385→#1404 corrigiram diversos problemas reais de isolamento SQLite, CAS, recuperação e coerência local. Seus testes específicos passaram em Windows e Ubuntu, mas a **Quality original continua RED**. A repetição de “85 históricos” é insuficiente sem referência exata às 85 ocorrências e seus motivos; elas não devem sumir por troca de branch, alteração de seleção, whitelist, mock de autoridade ou reclassificação artificial como PASS.

**Fonte autoritativa deste snapshot:**

- PR Draft de origem: [#1404](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1404)
- HEAD exato: `0630441417fb1ec0e42a06ca0b104a311a6de399`
- GitHub Actions: [run #39636432738](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39636432738)
- Job Quality: `119348084463`
- **588 módulos canônicos; 6.895 testes; 6.810 PASS; 51 FAIL; 34 ERROR**
- Security A74 = 365 PASS; H0 A79 = 64 PASS em jobs separados, sem permissão de Worker.

O arquivo `docs/aion/evidence/aion_p0_quality_85_red_baseline_20261021.json` registra os **85 cabeçalhos completos**, tipo `FAIL/ERROR`, módulo e exceção/assertion observada, vinculados ao SHA/job acima. `observed_exception` é evidência de log, não diagnóstico de toda a causa interna de cada teste.

## Classificação de triagem (não equivale a homologação)

| Família técnica | Ocorrências | Resultado concreto |
| --- | ---: | --- |
| `INDEPENDENT_PRODUCER_GATE` | **32 ERROR** | 23 de Outbox, 9 de Saga. Os rastros devolvem `INDEPENDENT_PRODUCER_NOT_ENROLLED`, `INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED` ou `INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED`. Os testes antigos esperam continuar após um boundary externo não matriculado. |
| `LEGACY_ACTIVATION_PLAN_EXPECTATION` | **3** | 1 FAIL + 2 ERROR no gate de reativação. Os dois ERROR são `KeyError: 'plan'` após `prepare_global_worker_activation_plan` retornar `BLOCKED` sem `plan`; o código atual bloqueia intencionalmente a emissão de plano sem `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`. |
| `LEGACY_WORKER_EXPECTATION` | **50 FAIL** | Worker runtime, Global Worker, readiness, activation, live verification e A76. Testes antigos esperam `READY`, `ACTIVATION_PLAN_READY`, `CONFIRMED` ou efeitos, mas os novos gates mantêm `BLOCKED` ou 0 execuções. Essa classificação **não** prova que cada implementação esteja correta; requer revisão individual após a homologação real. |

**Ponto decisivo:** para resolver os 32 ERROR não se pode inventar issuer, assinatura com chave do próprio chamador, reenvio automático, efeito local ou adapter com idempotência inexistente. Para resolver os dois `KeyError: 'plan'` não se deve criar `plan` ativável ou usar a presença da chave como autorização. Uma autorização externa independente real e validada é pré-requisito, junto com ensaios de recuperação e histórico.

## Ferramenta de comparação somente leitura

`tools/aion_p0_quality_red_ledger.py` implementa um comparador de evidências com dois modos:

```bash
python -B tools/aion_p0_quality_red_ledger.py --check-ledger
python -B tools/aion_p0_quality_red_ledger.py --compare-log caminho/para/log-completo-da-quality.log
```

A comparação com um log de *novo* job Quality requer saída completa de 588 módulos, 6.895 métodos, número final de falhas/erros, SHA exato e cada cabeçalho `FAIL/ERROR`. Detecta testes surgidos, desaparecidos, duplicados, resumo truncado ou seleção diferente. Um erro desaparecido é classificado como **mudança exigindo revisão humana**, nunca como GO automático. Não executa testes, não modifica SQLite, não lê credenciais nem chama provedores.

**Atenção ao fluxo:** esta ferramenta não substitui a execução canônica. A CI original continua selecionando seus testes integralmente, inclusive os 85 que falham. O job de auditoria adicional apenas valida o manifesto e 14 verificações adversariais do parser nos dois SO. Uma nova execução canônica deve ter seus resultados comparados ao manifesto por evidência, não apenas igualando números totais. Igualdade de identificadores não atesta igualdade dos rastros ou da causa.

## Próximo passo de engenharia, sem atalhos

1. Consolidar o stack Draft sem merge prematuro, certificando por evidência a integridade e a independência das fontes de prova de operação H0.
2. Capturar os contratos reais do fornecedor (por exemplo, o provedor de mensagens pode não oferecer token nativo de idempotência; lista de mensagens não comprova ausência definitiva).
3. Conseguir matrícula/verificação de chaves por custodiante independente, recibo de reserva da primeira tentativa e recibo/cabeça monotônica independente, com nonce único durável, reconciliação causal, rollback e perda de resposta.
4. Apenas depois avaliar o fluxo habilitado em ambiente controlado e os contratos legados Worker/Activation; nunca ocultar ou “limpar” o resultado Quality com mocks falsos de autoridade.

**Restrições irrevogadas nesta PR:** sem merge/deploy, Worker OFF, ZERO_AUTO_RESEND, nenhuma primeira operação de fornecedor, nenhuma assinatura externa alegada e nenhum gasto. **0/6 P0 homologados · HARD NO-GO**.
