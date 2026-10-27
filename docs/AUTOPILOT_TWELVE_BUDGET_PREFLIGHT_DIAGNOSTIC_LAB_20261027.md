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

## Reforço de integridade — arquivos obrigatórios e cache preservado

A leitura genérica anterior convertia HTTP 404 em um `default` sem erro. Na inicialização crítica, agora usamos um marcador de identidade local para distinguir arquivo realmente ausente de um JSON vazio legítimo. Status anterior, scanner e cache compartilhado são obrigatórios e precisam ter a estrutura esperada. Não há requisição adicional: continuam sendo três leituras.

O cache só substitui o estado em memória depois de essas leituras passarem. Se o controle persistido estiver `CONTROLE_INDISPONIVEL`, a etapa final **não regrava o cache compartilhado**, evitando apagar séries por consequência de uma leitura falha. Instalações sem os arquivos exigidos ficam bloqueadas e precisam de provisionamento auditado.

**Não foi comprovado** que esse comportamento tenha originado o cache vazio observado às 08:22 UTC. A alteração é preventiva e não substitui a telemetria sanitizada.

## Verificação e limite

- `test_autopilot_budget_preflight_diag_lab.py`: **19 testes sintéticos isolados** (15 anteriores + 4 novos para arquivo ausente, estrutura inválida, preservação de cache em memória e guarda AST da escrita). Nenhum teste importa/executa o Autopilot completo nem aciona Twelve Data.
- [CI dedicado #40512361958](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40512361958): **19/19 Ubuntu e 19/19 Windows** aprovados. A suíte de qualidade geral possui execução separada e deve ser conferida até conclusão.
- Isso não prova end-to-end no runner real. Requer revisão antes de qualquer merge e, em caso de futura liberação do código, comparação da nova etapa registrada com logs de runtime de uma execução normal já agendada. Não rodar artificialmente para diagnosticar.
- Nenhuma inferência de 28 pares observados a partir de cache vazio; o laboratório Trader da PR #1633 permanece separado.
- AION continua **0/6 P0, HARD NO-GO**, sem Worker/deploy/SEND.

## Evidências

- [Status do Autopilot](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/atlasquant-runtime/dados/autopilot_status_v107.json)
- [Orçamento persistido](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/atlasquant-runtime/dados/twelve_budget_v1108.json)
- [Run 40472852203](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40472852203)
