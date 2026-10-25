# AtlasQuant / AION — G55 reconfirmação estrita da projeção local JSON
**Data:** 2026-10-25. **Branch LAB:** `lab/aion-a190-g55-reconfirm-projection-integrity-20261025`, empilhada sobre G54. **0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**

## Objeto da correção

O caminho direto `ExecutionOutbox._confirm(..., fence_lab=None, reconcile_snapshot_lab=None)` retornava de modo idempotente quando a linha SQL estava `CONFIRMED` e o efeito local batia com o ledger, **antes** de verificar `action_outbox.data`, mesmo com `strict_projection_lab=True`. O resultado era sucesso com projeção local adulterada (estado, geração, identidade, JSON inválido ou chaves repetidas), sem reparação explícita. É problema de integridade **local**, não demonstração de efeito financeiro externo.

## Revisão independente do Codex

Codex CLI Windows 0.164.0-alpha.11.1, model `gpt-6.1-sol`, com `-s read-only --ephemeral`; sem edição de arquivos, testes, provider ou rede:
- Sessão `01a173f2-67e7-7a62-b01d-4a1730512f94` revisou G54 e recomendou rejeitar projeção divergente antes do retorno antecipado, reutilizando `_g43_projection_candidate_lab` e **não** `_g43_sync_projection_in_tx_lab` (que poderia reparar os dados).
- Sessão `01a173f5-8498-7211-aaae-666b161ce0a5` revisou o patch G55, confirmou o escopo estrito e sugeriu testes de formatação não canônica, precedência do erro G42 e comportamento com flag desligado. Essas três verificações foram incorporadas e executadas pelo operador, não pelo Codex.

## Evidência verificável — RED antes da correção

1. Testes G55 criados e versionados primeiro em `9b56df056cda6473d1970deacc40eaeb4a039d5f`.
2. Execução Windows em SQLite sintético descartável, contra código G54 **sem patch**: **8 casos; 3 PASS, 5 FAIL** (G55 02–06). O motor aceitou reconfirmação direta com `action_outbox.data` adulterado, mesmo com `strict_projection_lab=True`.
3. Patch mínimo no código no commit `b45f1c91737cee94fb572216792eda17354ddafd`: no retorno antecipado da reconfirmação direta `CONFIRMED`, compara candidato canônico `_g43_projection_candidate_lab(existing_state)` contra `existing_state["data"]`, **somente quando strict_projection_lab está ligado**. Divergência levanta `G55_CONFIRMED_PROJECTION_INTEGRITY_DENY`; documento inválido/identidade forjada retêm erros G43. A transação é revertida em caso de erro. O mecanismo **não repara** o JSON.
4. Mesmos 8 testes depois do patch: **8/8 PASS**; regressões G54, G53, G52 e G43 também PASS.
5. Três testes adicionais recomendados pela segunda revisão Codex foram acrescentados no commit `e3dd0888b72d93d222c6164e9ea9bc2c51bde3ee`: formatação JSON semanticamente equivalente porém não canônica, prioridade de `G42_CONFIRMED_LEDGER_INVARIANT_DENY` se ledger também está inconsistente, e compatibilidade flag-off sem reparo. **11/11 G55 PASS**.
6. Workflow Windows/Ubuntu matricial `.github/workflows/aion-a190-g55-reconfirm-projection-lab.yml` atualizado no commit `da4e445c9f51b3d5aa15d3dc447cd2b76ef22c03`, prevendo 11 novos mais 472 herdados = **483 testes por sistema**.

## Validação completa, commit testado

Windows isolado: `C:\Users\apare\AtlasQuant-G55-Projection-LAB-20261025`. No **SHA exato `da4e445c9f51b3d5aa15d3dc447cd2b76ef22c03`**, `unittest discover` percorreu sucessivamente G55, G54, G53, G52 e G50–G30 (G51 está incorporada como segunda suíte G50). Resultado: **483/483 PASS, exit code 0, checkout limpo**. A contagem é de casos sintéticos focados, não de P0 homologados.

**CI GitHub NÃO VERIFICADO para G55:** não havia PR G55 aberta nem workflow run associado ao SHA de teste no momento da consulta. A tentativa de abrir G54 Draft havia sido barrada pelas configurações de segurança da ferramenta; não contornamos o bloqueio. A presença do arquivo workflow na branch **não** constitui execução Ubuntu/Windows aprovada. O commit deste próprio relatório é posterior ao código testado.

## Restrições e próximo alvo

- Ainda não foram testadas nesta G55 falhas injetadas de COMMIT após efetivação incerta, rollback que falha e interrupção abrupta; precisam de laboratório separado **G56 candidato**, com ausência de retry automático e quarentena explícita.
- Comparação canônica com serialização bruta rejeita até diferenças puramente textuais em modo estrito; comportamento intencional e explicitamente coberto.
- Nada aqui prova identidade externa HUMAN_OWNER, recibo assinado por fornecedor confiável, primeira tentativa recuperável diante de resultado desconhecido, efeito único semântico entre request IDs, resistência a rollback físico, custódia monotônica independente, disponibilidade H0 real, nem a Quality/Security canônica. Achados históricos de dependências exigem auditoria separada.

**0/6 P0 · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
Nenhum merge na main, deploy, Global Worker, callback de fornecedor, cliente, operação financeira real, segredo, instalação ou gasto.
