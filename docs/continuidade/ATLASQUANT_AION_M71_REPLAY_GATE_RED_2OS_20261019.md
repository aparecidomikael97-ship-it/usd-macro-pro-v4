# AtlasQuant / AION — M71: RED adversarial de replay de gate READY após reabertura

**Data:** 19/10/2026. **Veredito:** RED_LAB_NEW_SECURITY_CONTRACT (Ubuntu e Windows); HARD NO-GO operacional. Não ocorreu ativação nem execução de Worker.

## Origem / escopo
- Branch de laboratório isolada: `lab/aion-m71-reopened-ready-gate-replay-red-20261019` criada de M70, que herda A118 original pinado `c62fab663c6349d7320f7843c8d09587c514426b`.
- Teste novo: `test_aion_m71_stale_gate_replay_negative.py` em commit `8723b6d834f796126f86e0fb1d1be77f8679e9c3`. CI `.github/workflows/aion-m71-stale-gate-replay-red-lab.yml` em commit `5220b24a244295eccaff2b86b4f8d677932b8c77`.
- **[Run M71 #39264761619](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39264761619)**, jobs Ubuntu `118101337992` e Windows `118101337603`.
- Ambos: verificação `A118_ORIGINAL_4_BLOBS_MATCH` PASS; controles M68 originais **2/2 PASS por SO**; teste adversarial novo **1/1 FAIL por SO**; log `AssertionError: 'READY' != 'BLOCKED'` e `M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT`.

## Sequência reprodutível (inteiramente com fixtures originais)
1. Gerar ambiente de fechamento durável e reconciliação segura por fixture original; avaliar gate `REACTIVATION_GATE_READY` em NOW.
2. Após dez segundos simular observação de incidente reaberto `REOPENED`; nova reconciliação resulta em gate `REACTIVATION_GATE_BLOCKED`, contendo `ACTIVE_GLOBAL_WORKER_INCIDENT_PRESENT`. Esse bloqueio funciona.
3. Usar mapeamento de `approval` **mínimo, sintético, não assinado e não emitido**, apenas para exercer o contrato negativo da função `validate_reactivation_gate_for_execution`.
4. Passando gate NOVO BLOCKED, o validador retorna BLOCKED (controle correto). Reapresentando gate ANTIGO READY dentro dos 300s de TTL, com o mesmo checkpoint/ledger/flag, o validador retorna **READY** apesar da observação reaberta. A assertiva de segurança BLOCKED falha em Ubuntu e Windows.

## Diagnóstico e impacto delimitado
- Lacuna demonstrada: o validador direto verifica integridade/TTL da estrutura do gate e igualdade com runtime/ledger/flag/approval, mas não recebe/verifica por conta própria uma nova observação de reconciliação. A reapresentação de evidência ainda válida no tempo não garante que o incidente continua fechado.
- **Não é bypass operacional comprovado.** O dado `approval` da sonda não é ticket real; os guards de emissão/validação de autoridade independente no A118 continuam negando ativação. Nenhum writer, provider, feature flag ou Worker foi invocado pelo M71.
- Limite: o teste não demonstra que a UI/caller real recicla o gate antigo. Demonstra que a função pública de validação isolada aceita esse gate quando fornecido.
- Classificação: **risco latente para futura integração**, demanda revisão independente e prova end-to-end dos callers. Não atribuir P0 homologado nem declarar exploração em produção.

## M72 — plano recomendado para LAB (não executado neste checkpoint)
1. Definir contrato de revalidação obrigatória do estado de incidente IMEDIATAMENTE antes da possível habilitação; originar estado de uma fonte confiável com marcador monotônico (revisão / epoch / digest), não de mapeamento controlado pelo chamador.
2. Negar se houve novo incidente depois de `gate.created_at` ou se fonte/epoch é indisponível, sem possibilidade de usar READY antigo dentro da TTL.
3. Testes RED antes da alteração: (a) gate pronto antes de REOPENED; (b) novo incidente distinto; (c) snapshot indisponível ou desatualizado; (d) mudança entre leitura de estado e futura escrita; (e) replay de gate até TTL; (f) política ZERO_AUTO_RESEND e ausência de escrita.
4. Corrigir SOMENTE em LAB após revisão das interfaces de uso, sem remover proteções de autoridade; validar Linux+Windows, integrações e histórico canônico; PR Draft se pertinente, nunca merge/deploy.
5. Registrar evidências e resultados não aprovados sem silenciar o RED ou afrouxar testes.

## Estado
M70 candidato: 17/17 PASS Linux e 17/17 PASS Windows [run #39264063899](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39264063899), sem integrar a suíte histórica. M71 NOVO RED em dois SO. Quality histórico ainda 50 FAIL/34 ERROR, incluindo três registros de reativação originais. **0/6 P0 homologados. Worker OFF, sem merge, deploy, gasto adicional ou autoridade F1/T1. HARD NO-GO.**
