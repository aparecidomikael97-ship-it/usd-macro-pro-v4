# AtlasQuant / AION — M72: análise de alcance do RED M71 no caminho real de ativação

**19/10/2026. Análise estática somente, SEM reexecução de UI, sem ativação, sem mudança de código de produto.**

## Evidência
- M71 [run #39264761619](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39264761619): Ubuntu e Windows reproduzem `AssertionError: 'READY' != 'BLOCKED'` ao passar um gate antigo READY após um incidente REOPENED a `validate_reactivation_gate_for_execution`. Controles negativos originais M68 passam. Não há ticket válido na sonda.
- Módulo `atlasquant_aion_global_worker_reactivation_gate.py` A118 original blob `8412ada82761de37a72a8f29af7f8672cfb5b082`, linhas 448–550: valida ledger runtime, integridade/TTL do gate, igualdade SHA/digest/flag/approval. **Não recebe a fotografia de incidentes atual**, portanto não consegue observar reabertura que não modificou esses inputs.
- `atlasquant_aion_global_worker_activation.py` A118 original blob `df43bb4371c784396069f4ede51205b0aa19cc0a`, linhas 614–709: wrapper primeiro executa `validate_global_worker_activation_approval` (A74 nega autoridade local) e só depois chama `validate_reactivation_gate_for_execution` com o gate fornecido pelo caller. A proteção de autoridade atual impede o cenário operacional; não provar que não existam outros chamadores externos.
- `atlasquant_aion_admin.py` do A118, linhas 9000–9100: na interface, quando `activation_approval.post_incident_gate_required` é verdadeiro, há tentativa de **reler runtime + flag + live verification + supervision + reconcile + assess** antes de invocar `activate_global_worker_feature_flag`; erro de leitura retorna gate BLOCKED e interrompe chamada. Portanto **o trecho observado da UI usa rechecagem fresca**.
- Isto reduz o alcance observado: falha comprovada é da função **direta**, não exploração end-to-end do caminho admin. A UI foi lida estaticamente; não passou por ensaio dinâmico M72.

## Contrato-alvo de correção (P0 de integridade futura, sem declarar homologação)
- Boundary de habilitação não deve confiar só em gate armazenado pelo caller dentro de TTL. Deve exigir evidência atual de incidente de origem confiável, associada à mesma leitura fresca de runtime/flag, com cursor monotônico/epoch ou prova equivalente, digest e timestamp, e negar se falta, diverge ou houve REOPENED / OPEN_NEW_AFTER_CLOSURE.
- As mudanças de incidentes entre avaliação e eventual escrita exigem solução de **TOCTOU** (lease/fence ou checagem atômica com fonte de autoridade), não apenas mais um campo `checked_at` informado pelo caller.
- Um parâmetro opcional alimentado pelo mesmo caller não resolve o problema se for falsificável; exigência deve ficar no executor/guard com prova independente.
- Novo teste dirigido RED deve cobrir replay READY, incident snapshot indisponível, novo incidente, mudança do epoch, e validação negativa do wrapper e invariantes sem side effects.
- Só após arquitetura e revisão independente: patch LAB + 2 OS + Quality/Security histórico, PR Draft (sem merge), sem fragilizar guard de autoridade.
- Manter separados RED de M71 (latente) e três REDs legados (incompatibilidade de expectativas).

## Estado
- M70 candidato 17/17 OK em Ubuntu e Windows, mas **não substitui suíte original**.
- M71 novo RED confirmado nos dois SO.
- M72 apenas classificação e desenho, não é correção.
- 0/6 P0 homologados; Worker OFF; ZERO_AUTO_RESEND; nenhum deploy, merge, gasto novo ou aprovação independente. **HARD NO-GO**.
