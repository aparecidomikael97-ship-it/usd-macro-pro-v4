# AION M71 — mitigação de replay de gate READY em validação de execução (LAB deny-only)

**Data: 19/10/2026. Veredito: correção LAB restrita à barreira de execução, NÃO HOMOLOGAÇÃO.**
**0/6 P0 homologados · HARD NO-GO · Global Worker OFF · ZERO_AUTO_RESEND · sem merge/deploy/custo.**

## Defeito reproduzido com A118 ORIGINAL

`validate_reactivation_gate_for_execution` em `atlasquant_aion_global_worker_reactivation_gate.py` recebia apenas `runtime_result`, `flag_evidence`, `activation_approval` e um `gate` potencialmente reapresentado pelo caller, com `now`. Um gate `REACTIVATION_GATE_READY` emitido antes de incidente REOPENED podia continuar válido dentro de TTL=300s se runtime/ledger/flag não mudassem. Não havia leitura fresca e independente da fonte atual de incidentes naquele ponto. O retorno direto podia ser `state=READY`; **isso NÃO era bypass real do Worker**: o writer `_independent_activation_authority_denial` no A118 bloqueava a ativação mesmo após esse validador.

O teste original negativo `test_aion_p0_m71_original_stale_gate_safety_negative_lab.py`, que exige `state=BLOCKED` sem mudar sua assertiva, foi reexecutado ANTES do patch na branch LAB:
- [**CI RED #39335221061**](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39335221061), Ubuntu e Windows **failure** em `Original M71 SECURITY EXPECTATION WITHOUT XFAIL`;
- ambos exibem `AssertionError: 'READY' != 'BLOCKED'`, `M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT`, com quatro fontes de Writer/Outbox/incident source preservadas por SHA.
- O teste não emite aprovação real nem escreve flag, e o fixture de incidente não é credencial de produção.

## Correção deliberadamente limitada

Arquivo LAB `atlasquant_aion_global_worker_reactivation_gate.py`: depois de todas as verificações locais usuais (integridade, expiração, SHA runtime, digest do checkpoint, ledger, latest closure ID, approval e estado da flag), os caminhos que antes retornavam `READY` na validação de **EXECUÇÃO** agora retornam sempre:

```json
{
  "state": "BLOCKED",
  "reason": "INDEPENDENT_POST_INCIDENT_CURRENT_STATE_NOT_ENROLLED",
  "reactivation_authorized": false,
  "feature_flag_modified": false,
  "global_worker_executed": false
}
```

Isto cobre **gate requerido, localmente READY** e **gate não requerido por ausência de histórico** — ausência que também pode resultar de rollback. O retorno não invoca um witness, não aceita `verified=true` no approval, não mantém janela de liberação por TTL e não faz retry. Gates já inválidos continuam retornando as razões de erro específico existentes. Nenhuma exceção foi concedida para caller ou teste.

**Importantíssimo:** isto é uma **trava temporária de recusa**. NÃO deteta a reabertura por consulta viva, NÃO autentica a origem do incidente e NÃO substitui enrollment externo. `assess_post_incident_reactivation_gate` e `validate_reactivation_gate_for_plan` são diagnósticos/planejamento e podem continuar relatando READY com fixtures, mas o validador final pré-escrita de flag nega. A própria `activate_global_worker_feature_flag` do A118 também nega por autoridade independente não matriculada. Para alguma liberação futura seria preciso projeto e homologação de novo protocolo, não trocar um booleano ou apagar o return BLOCKED.

## Evidências exigidas antes de retirar a trava

1. Fonte **fora do caller, Worker, host e domínio de restauração** para incidentes atuais/reativações, administrada por identidade independente com chave/issuer autenticado; ledger monotônico `owner/tenant/workspace/host/epoch/sequence`.
2. Leitura CURRENT sincronizada imediatamente antes da **escrita final de flag**; reabertura detectada mesmo dentro dos cinco minutos do gate antigo; replay, falta de resposta ou fonte desatualizada bloqueiam.
3. Anti-TOCTOU com CAS/fence da sequência de incidente e emissão de autorização de uso único para a transição final; validade de gate não é evidência de estado externo atual.
4. Contas e permissões segregadas, nonce consumido uma vez e assinado; recibos válidos amarrados à identidade HUMAN_OWNER real, source trust e escopo; autenticação do produtor segue P0 distinto.
5. Testar duas máquinas, rollback de backup do AION e custodiante, pós-reboot físico Windows, revogação, atualização concorrente de incidente, perda da resposta, liberação expirada e ausência de auto reenvio.
6. Quality e Security canônicas: Quality histórico `6.562 / 51 FAIL / 34 ERROR` no baseline antes do patch. **Não executar/alegar homologação de Quality com a CI focada desta alteração.** Os testes históricos de fluxos positivos de reativação podem passar a falhar em LAB porque o novo deny substitui READY por BLOCKED; não silenciar esses testes, e só reconciliá-los com contrato seguro aprovado.

## Suítes focadas

- `test_aion_p0_m71_original_stale_gate_safety_negative_lab.py`: assertiva ORIGINAL de segurança ainda espera BLOCKED. Seu resultado GREEN após patch significa que o gate stale não pode mais retornar READY, não que fonte externa está verificada.
- `test_aion_m71_unenrolled_current_incident_source_lab.py`: dez testes: READY recente válido bloqueado, replay após REOPENED, `verified` autoafirmado, histórico sem closure, digest inválido, TTL expirado, input imutável e approval inconsistente.
- `test_aion_p0_original_six_evidence_matrix_lab.py`: os seis P0 continuam abertos e o teste 08 foi **revisado explicitamente para exigir GREEN** do mesmo teste M71 após a mitigação. A matriz conserva as evidências da execução original RED; esta alteração no auditor NÃO modifica a assertiva original M71.
- `.github/workflows/aion-m71-fresh-incident-source-deny-lab.yml`: Ubuntu+Windows, `contents:read`, gates de Worker/Outbox/activation pins, dependências rastreadas, 1 M71 original + 10 negações + 10 registro P0 + 9 A73/A110 por SO; sem Cloudflare/AWS/provedor/Worker/credenciais.

**0/6 P0 homologados, HARD NO-GO preservado.** A mitigação ainda precisa de revisão humana independente antes de qualquer integração ou reuso em produção.
