# AION M71 — Validador de gate de reativação com negação na ausência de incidente fresco independente

**19/10/2026 — GO-LAB PARA O GUARD DIRETO SOMENTE. NÃO HOMOLOGADO. 0/6 P0, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy/gastos.**

## Falha real e origem imutável

A implementação A118 `atlasquant_aion_global_worker_reactivation_gate.py`, blob Git `8412ada82761de37a72a8f29af7f8672cfb5b082`, possui `validate_reactivation_gate_for_execution()` que examina `gate_digest`, `expires_at`, runtime/closure digest e approval, mas não consulta uma fonte independente dos incidentes **imediatamente antes da habilitação**.

Se um incidente já fechado é reaberto 10 segundos depois da criação de um gate `READY`, a reavaliação local correta devolve `BLOCKED`, porém uma chamada posterior com o gate antigo ainda dentro de seu TTL (até 300s padrão) **aceita `READY`**. O teste negativo original `test_aion_p0_m71_original_stale_gate_safety_negative_lab.py` (condição de segurança `state=BLOCKED`) REPRODUZ o RED. Ações de efeito do Worker/Outbox já são barradas por testemunha e produtor não matriculados; não alegar efeito operacional ocorrido.

### Red original desta rodada

- Branch `lab/aion-m71-fresh-incident-execution-hardstop-20261019` derivada de `44a4de01817d896e056810025d6c68ec8e34112f`.
- Testes **congelados antes de modificar o validador**, `test_aion_m71_execution_fresh_source_denial_lab.py`, commit `ee8004ef18531e67187c5c116ba5198884d78a52`: 12 cenários de gate reaberto, gate READY dentro de TTL, ausência de histórico local, falsa assinatura/verified no gate ou approval, plano ainda apenas de planejamento, expiração, alteração de runtime/approval, gate bloqueado e mismatch.
- CI da implementação original `#39335321672` <https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335321672>: no Ubuntu, **6 FAIL/12** novos (os seis casos sem testemunha retornaram indevidamente `READY`); o teste M71 original **1 FAIL/1**, mensagem `M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT`. Os jobs canônicos legados mais amplos TAMBÉM falharam no baseline, antes da correção: reactivation `1 FAIL + 2 ERROR` e activation `15 FAIL`. Não atribuir esses erros preexistentes ao patch.

## Correção mínima no guard direto, sem fonte falsa

Commit `c78b0f2a783040bd981c895aff9436642f6f48ae`, alteração SOMENTE de `atlasquant_aion_global_worker_reactivation_gate.py`, blob `8533ae3c1720d4230dace6478a40f9f11b9677d4`:

1. Se a leitura local do runtime diz que o gate não é necessário, **NÃO** retornar `READY` ao validar execução: a ausência de histórico local pode ser consequência de rollback. Retorna `BLOCKED/FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED`.
2. Se gate é necessário, manter todos os bloqueios de integridade, expiração, escopo, fechamento e approval; se passarem, **AINDA** retornar `BLOCKED/FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED`. Um digest local e TTL nunca validam atualidade de incidentes depois da criação do gate. A checagem da fonte independente não existe, então não há caminho de liberação.
3. Não alterar `assess_post_incident_reactivation_gate` nem `validate_reactivation_gate_for_plan`: um gate `READY` ainda pode significar **pronto para planejar**, não autorizado a habilitar Worker.
4. Nenhum `verified=true`, callback, função mock, assinatura local ou toggle permite retornar `READY` em `validate_reactivation_gate_for_execution`. A futura alteração requer matrícula de issuer/fonte independente e readback monotônico, com revisão humana.
5. Código `atlasquant_aion_global_worker_activation.py` permaneceu EXATAMENTE blob `df43bb4371c784396069f4ede51205b0aa19cc0a`; sua barreira de autoridade independente continua intacta. Outbox/Worker não foram alterados.

## Green limitado e regressões históricas

[Actions #39335459200](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335459200), após patch, matriz Ubuntu + Windows: **12/12 casos novos PASS e 1/1 M71 original negativo PASS em cada SO**. O test original permaneceu inalterado e a sua afirmação continua exigindo `BLOCKED`.

**O workflow maior permanece FAILURE**, porque repete os legados históricos já RED no **baseline**: reactivation `1 FAIL + 2 ERROR` antes e depois; activation `15 FAIL` antes e depois. Esses números não são homologação e nenhum teste foi `xfail`. Uma CI focada separada `.github/workflows/aion-m71-exact-original-replay-focused-lab.yml` deve mostrar 13/13 em cada SO após concluir; ela não substitui Quality completa nem cancela o vermelho histórico.

## Limites e próximos passos

1. A correção nega habilitação **por falta de uma fonte fresca realmente independente**; não matriculou tal fonte, não integra alta-water e não resolveu os seis P0. Trata-se de HARDSTOP, não de um protocolo de reativação operacional.
2. `validate_reactivation_gate_for_plan` continua podendo produzir `READY` para análise. Não confundir plano com autorização final; ação real permanece bloqueada.
3. O gate direto fica permanentemente `BLOCKED` para execução nesta versão, inclusive quando o incident snapshot local é `CLOSED_HISTORY_RECOGNIZED`. Esse trade-off de disponibilidade é intencional em HARD NO-GO.
4. O M71 era transversal aos seis P0, não substitui nenhuma identidade, recibo, recuperação incerta, H0 físico ou os P0 SQLite canônicos.
5. Falta revisão Quality/Security do ramo integrado (Quality histórica 51 FAIL e 34 ERROR; Security 365 PASS em seleção anterior), migração de contratos históricos obsoletos sem reduzir cobertura, witness H0 externo e auditoria independente. O teste de registro dos seis P0 que ainda espera M71 RED precisa ser migrado explicitamente e confrontado com a evidência original RED, não simplesmente removido.
6. Testes de gate/imitação não demonstram efeito do provedor, Worker operacional ou homologia de P0. Sem merge, deploy, custos, contas ou produção.

**Conclusão:** replay M71 não obtém mais READY no validador final em LAB. Status operacional: HARD NO-GO, 0/6 P0, Worker OFF, ZERO_AUTO_RESEND.
