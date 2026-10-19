# AION — checkpoint M64 | Fronteira de autoridade do produtor e do admitidor

**Data:** 2026-10-19. **GO-LAB documental / NO-GO integração / HARD NO-GO operação.**

**Escopo e origem:** leitura direta e conferência de blobs no A118, PR Draft [#1326](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1326), HEAD `c62fab663c6349d7320f7843c8d09587c514426b` (aberto e não mesclado nesta consulta). O M63 já está registrado na mesma branch de documentação. Computador remoto OFFLINE; sem Codex nesta etapa, sem executar suítes A118, sem código de produto, sem deploy, Worker ou gasto.

## Resultado técnico: quatro autoridades diferentes, não intercambiáveis

| Papel | Código A118 inspecionado | O que existe e pode ser afirmado | O que NÃO foi comprovado |
|---|---|---|---|
| Identidade/sessão ADMIN | `atlasquant_aion_core_runtime_bridge.py:41–94`, `authenticated_context` | Vincula Context a sessão host previamente autenticada, requer `role=ADMIN`, permissão e fingerprint. Declara que identidade não vem de request body/modelo. | Matrícula ou prova independente de que **um sensor/producer** emitiu o dado OPEN/REOPEN; papel ADMIN não é autorização para inventar observação. |
| Evidência do runtime | `atlasquant_aion_core_runtime_bridge.py:127–184`, `_evidence_from_row`; `atlasquant_aion_global_worker_live_verification.py:85–327` | A ponte rotula fonte/observação com limites de formato, origem e frescor. Seu próprio texto declara que a identidade externa da fonte **não é independentemente autenticada aqui**. LIVE exige flag ENABLED; evidência positiva independente não matriculada é bloqueada. | Que `truth_state=CONFIRMED`, `Origin.SYSTEM_OBSERVED`, `evidence_state=CONFIRMED`, digest ou recibo local certifique produtor real. |
| Controle STOP/REENABLE | `atlasquant_aion_incident_control_plane.py:61–239`, `evaluate_control_request` | Avalia ator, escopo, capabilities de controle e alegada verificação, mas a saída `MAY_PROGRESS_TO_MUTATION_GATE` é **somente candidatura a gate posterior**: `grants_authority=False`, `executes_action=False`. | Capability `incident_control:*:stop/reenable` ser autorização de **admissão/commit** de OPEN/REOPEN. `authority_verification` como dicionário de entrada, isoladamente, não prova assinatura/âncora externa. |
| Fechamento durável | `atlasquant_aion_global_worker_durable_incident_closure.py:320–380,736–815` | Fluxo próprio de fechar decisão com sessão ADMIN, plano, aprovação/segunda confirmação, preflight e persistência CAS/readback. | Que tal permissão feche também o estado compartilhado da **abertura** ou conceda direito para escrever evento OPEN/REOPEN. |
| Proposta de incidente | `atlasquant_aion_global_worker_supervision.py:135–249`; `atlasquant_aion_global_worker_incident_reconciliation.py:237–430` | Classifica evidência local, produz `INCIDENT_PROPOSED`, projeta OPEN/REOPENED junto de histórico de FECHAMENTOS; nenhuma mutação declarada. | Quem admite o OPEN, vincula identidade causal e confirma seu commit durável antes da rechecagem final. |
| Ativação do Worker | `atlasquant_aion_global_worker_activation.py:211–224,365–407,502–553,638–705` | Local READY/approval não são raiz independente; o fluxo de ativação termina em `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED`. | Qualquer GO operacional, integração homologada, ou permissão para habilitar Worker. |

### Veredito da busca

**Não foi demonstrada no fluxo A118 examinado uma autoridade inscrita que possa aceitar e persistir oficialmente OPEN/REOPEN com origem, identidade causal, escopo e revisão verificáveis.**

Esta é uma **lacuna de cadeia de custódia**, e não prova de ausência absoluta de outros módulos ou de um ataque operacional. É inadequado escolher automaticamente o ADMIN, HUMAN_OWNER, Guardian/Sentinel, um journal genérico ou um `truth_state` como produtor autenticado. Um humano pode aprovar decisões críticas específicas, mas esse fato não define por si a procedência de uma observação técnica.

### Contrato mínimo a esclarecer antes do writer (proposta NÃO IMPLEMENTADA)

**Separar duas funções futuras:** (1) validador da **origem e evidência** do sinal; (2) admitidor da **transição durável** da ocorrência. A implementação/matrícula real de ambas segue sem prova.

| Fronteira | Prova mínima necessária | Sem prova |
|---|---|---|
| Identidade do produtor | Vínculo verificável a identidade efetivamente matriculada, versão/generation do produtor, domínio e escopo de runtime/tenant; autenticidade não derivada dos dados controlados pelo próprio remetente | `SOURCE_UNVERIFIABLE`; preservar observação diagnóstica, não admitir OPEN autoritativo |
| Evento e identidade causal | Evidência íntegra e ordenada de caso/observação; regra auditável de mesmo caso, outro caso ou UNKNOWN, sem fusão por motivo ou digest truncado | `CAUSALITY_UNKNOWN`; não fundir nem encerrar, veto a decisões permissivas |
| Admissão/commit | Capability de **escrita OPEN/REOPEN** específica e conferida fora do payload; CAS/ordem/época, idempotência e readback durável | `ADMISSION_NOT_PROVEN`; estado pendente bloqueia, não é histórico certificado |
| Histórico completo | Recuperar aberturas, reaberturas e fechamentos após reinício com flag DISABLED; detectar indisponibilidade, estado incompleto, revisão antiga e rollback dentro de fronteira de confiança demonstrada | `OPEN_SET_UNKNOWN`; nenhuma declaração de zero incidentes |
| Consumidor e efeito | Vincular revisão atual ao gate/plano/approval e revalidar imediatamente antes do writer; corrida ou efeito externo exigem protocolo/reconciliação que impeça falso GO | `BOUNDARY_UNPROVEN`; HARD NO-GO para efeito |
| Autoridade de ativação | Raiz HUMAN_OWNER/F1/T1/F2 e provas externas independentes, não criadas por teste ou status local | Continua `INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED` |

**Nota de segurança:** preservar sinais de risco mesmo sem autorização para criar o registro durável. Um observador não autenticado nunca deve poder eliminar um incidente anterior ou construir `CLEAR_AT_REVISION`. Uma leitura inteiramente vazia não é prova de completude. Falha na matrícula não pode ser contornada aceitando um booleano `authenticated=True`.

## Critérios adversariais prioritários para revisão futura (NÃO EXECUTADOS)

- T01: origem textual `source=aion_global_worker_live_verification` e `evidence_state=CONFIRMED` autodeclarados não matriculam produtor.
- T02: sessão ADMIN verdadeira sem prova de sensor externo não autoriza forjar OPEN/REOPEN.
- T03: dicionário `authority_verification` com `state=VERIFIED` não é prova de capacidade `incident:open:commit` e não pode permitir mutação real.
- T04: assinatura local/hash/TTL de um pacote produzido pelo solicitante não é autorização externa.
- T05: OPEN detectado sem possibilidade de commit não vira CLEAR; incerteza bloqueia qualquer futuro GO.
- T06: replay/rollback, mesmo com digests consistentes, não pode fazer revisão regressiva parecer atual.
- T07: CLOSE durável não suprime uma abertura posterior; ambos devem corresponder à identidade causal correta.
- T08: leitura com feature flag DISABLED precisa recuperar OPEN persistido sem depender de verificação LIVE positiva.
- T09: corrida entre verificação e efeito exige prova de linearização/reconciliação; sem isso, continuar NO-GO.

**Nenhum teste acima está contabilizado como PASS, FAIL de produto ou homologação.**

## Decisão M64 e próximo objetivo

**Decisão:** não usar um adaptador de storage nem alterar o campo de apresentação `CONFIRMED` para fabricar um estado positivo de autoridade. O próximo trabalho de maior valor não é aumentar a contagem de testes negativos, mas responder com **evidência independente**: `qual produtor realmente pode atestar OPEN/REOPEN no domínio Global Worker e qual serviço, previamente autorizado, admite a transição?`

Se ninguém puder demonstrar essa dupla autoridade no A118, registrar como **dependência externa/arquitetural não resolvida** e priorizar os P0 reproduzíveis localmente, sem transformar a dependência em uma implementação ilusória. O caminho pode continuar investigado no LAB, mas integração e operação permanecem bloqueadas.

## Controles e proveniência

Fontes GitHub conferidas no HEAD A118 (blobs):
- `atlasquant_aion_core_runtime_bridge.py` — identidade/sessão e evidência de runtime (hash fonte registrado por fetch).
- `atlasquant_aion_incident_control_plane.py` — políticas STOP/REENABLE.
- `atlasquant_aion_global_worker_live_verification.py` — `3cfd1926aac5b3768595cb3ffdfad6fed539490b`.
- `atlasquant_aion_global_worker_supervision.py` — `8a6ab6be8789deeeb80b6b2df39df9745d91e902`.
- `atlasquant_aion_global_worker_incident_reconciliation.py` — `85541bb2d10f0b97b096df10b5184851160cfec9`.
- `atlasquant_aion_global_worker_durable_incident_closure.py` — `3d7310ff055802f8a47651ac7d36521c0e0929e9`.
- `atlasquant_aion_global_worker_activation.py` — `df43bb4371c784396069f4ede51205b0aa19cc0a`.

**Estado mantido:** 0/6 P0 homologados, 3 REDs históricos da reativação não resolvidos, Quality A118 histórica 50 FAIL / 34 ERROR (sem reexecução M64), Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/novo gasto, nenhum cliente real. Revisão Codex/external não executada nesta rodada. Os PDFs/ZIPs anteriores não foram transferidos para o Windows offline nem para esta branch pública.
