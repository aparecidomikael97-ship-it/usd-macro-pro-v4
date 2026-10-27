# Autopilot — diagnóstico sem gasto da falha no orçamento Twelve (LAB, 27/10/2026)

**Status: PR Draft. Não mesclar, implantar ou disparar o coletor por esta evidência.** Nenhuma ordem, Worker, provider SEND, ativação de credencial, nova chamada Twelve Data ou aumento de orçamento é autorizado.

## Incidente observado (apenas leitura)

- Estado `atlasquant-runtime` de 27/10/2026 08:22 UTC: `twelve_block_type=CONTROLE_INDISPONIVEL`, `twelve_calls_this_run=0`, `scanner_ready=false`; arquivo compartilhado `dados/twelve_series_v1108.json` continha `{"series":{}}`.
- Registro do orçamento do mesmo dia: `used=14` de `limit=480` **interno**. Isso não comprova saldo real no provedor e não autorizaria consultas adicionais.
- Reprodução local do `Budget.bootstrap` + `summary` com os estados preservados: sem erro, sem bloqueio persistente e sem escrita simulada. A origem do erro real **não foi identificada**: poderia ocorrer na leitura remota ou em outra fase. Não atribuir causa sem telemetria específica.
- Código atual de `td_fetch` limita-se a sete pares USD; essa PR **não altera** o limite de escopo.

## Instrumentação proposta

`autopilot_v107._td_initialize()` conserva as três leituras existentes, o bootstrap do orçamento e o resumo. Adiciona somente o estágio em que a inicialização passou ou falhou, com códigos autorizados:

| Estágio | Significado |
| --- | --- |
| `READ_PREVIOUS_STATUS` | Falha ao ler status persistido |
| `READ_SCANNER` | Falha ao ler estado do scanner |
| `READ_CACHE` | Falha ao ler cache de séries |
| `BOOTSTRAP` | Falha na construção/reconciliação do orçamento |
| `SUMMARY` | Falha no resumo final |
| `COMPLETE` | Essas fases completaram; não significa autorização nem saúde dos preços |

O campo novo `twelve_budget_preflight` do status inclui apenas `state`, `stage`, `error_category` e três flags permanentemente falsas de autoridade (`authorizes_provider_call`, `automatic_retry_allowed`, `spend_authorized`). Mensagens de exceção, URLs, chaves e tokens são descartados; categorias desconhecidas viram `UNCLASSIFIED`. O bloqueio original `CONTROLE_INDISPONIVEL` permanece até uma inicialização válida.

**Importante:** mesmo o diagnóstico `COMPLETED_NON_AUTHORIZING` não significa que a quota do provedor, a fonte de mercado ou a proteção de execução estejam liberadas. As políticas já existentes continuam decidindo, e nenhuma delas foi afrouxada.

## Verificação e limite

- `test_autopilot_budget_preflight_diag_lab.py`: 15 testes sintéticos isolados para leitura de cada etapa, falha do bootstrap, falha do resumo, redaction de segredo, contador HTTP zerado, ausência de retry, bloqueio persistente e nenhum caminho novo de I/O. O teste compila apenas a função de preflight por AST, sem importar/executar todo o Autopilot.
- Resultado local: 15/15. O CI da PR deve confirmar Ubuntu e Windows.
- Isso não prova end-to-end no runner real. Requer revisão antes de qualquer merge e, em caso de futura liberação do código, comparação da nova etapa registrada com logs de runtime de uma execução normal já agendada. Não rodar artificialmente para diagnosticar.
- Nenhuma inferência de 28 pares observados a partir de cache vazio; o laboratório Trader da PR #1633 permanece separado.
- AION continua **0/6 P0, HARD NO-GO**, sem Worker/deploy/SEND.

## Evidências

- [Status do Autopilot](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/atlasquant-runtime/dados/autopilot_status_v107.json)
- [Orçamento persistido](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/atlasquant-runtime/dados/twelve_budget_v1108.json)
- [Run 40472852203](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40472852203)
