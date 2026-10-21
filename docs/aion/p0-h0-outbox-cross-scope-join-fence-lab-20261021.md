# AION P0/H0 — Isolamento de decisões por escopo nas consultas SQLite do Outbox (LAB)

Data: 21/10/2026. Alteração de defesa de dados **no código real de `ExecutionOutbox`**, mas ainda isolada em PR Draft, sem autorização de integração ou deploy.

## Falha real reproduzida ANTES da correção

As consultas de leitura `_outbox_row/get` e `list` realizavam:

```sql
FROM action_outbox o
JOIN action_decisions d ON d.decision_id=o.decision_id
WHERE o.owner=? AND o.tenant=? AND o.workspace=?
```

A linha externa `o` estava filtrada corretamente por escopo, mas o `JOIN` **não comparava `d.owner/tenant/workspace` ao escopo da própria `o`**. Diante de `action_outbox.decision_id` adulterado/comprometido para apontar ao `action_decisions.decision_id` válido de outro escopo, `get()`/ `list()` retornavam à conta de origem o `decision.data` estrangeiro (incluindo `payload`). O cenário depende de corrupção ou capacidade de alterar SQLite local, não demonstra uma exploração remota nem vulnerabilidade de rede. O ID referenciado por foreign key continua existente, portanto uma verificação apenas da FK não resolve a falha.

### Evidência RED-first

Bateria `tests/test_aion_p0_h0_outbox_cross_scope_sql_join_fence_lab.py` (11 testes contra SQLiteChatStore + ExecutionOutbox reais; dois escopos no mesmo DB), commit anterior ao patch `3d34426feb4c27313f1c3f8a3987a2bd5da1205b`, GitHub Actions #39610850400:

- **9 FAIL/11**, inclusive `LookupError not raised` e listas contendo o `payload` de outro owner, tenant ou workspace, após troca de decision_id por SQL na fixture.
- Um outro escopo legítimo continua tendo a própria decisão, e a chamada de claim deve permanecer sem efeito externo. Os testes não criam mensagem ou ação de fornecedor.
- Os resultados explicitam uma falha de confidencialidade **sob corrupção local**; nada prova vazamento efetivo para clientes reais.

## Correção de menor escopo

Atualizado `atlasquant_aion_execution_outbox.py` para associar também `owner`, `tenant` e `workspace` nas condições de quatro JOINs:

1. `_outbox_row` usado por `get`;
2. `list`, inclusive com filtro de estado;
3. leitura de idempotência preexistente em `enqueue`;
4. seleção de candidato para `claim_next`.

Para exemplos contaminados, **a linha sem correspondência do mesmo escopo desaparece da leitura**, `get` gera `LookupError` e `list` retorna lista sem a decisão de outro escopo. A decisão válida original de outro escopo não é apagada. A junção reforça isolamento já esperado, não modifica o gate obrigatório de fonte independente, o estado da operação externa ou a semântica de `NO_EFFECT_FENCED`.

A correção **não substitui** proteção do SQLite no disco, RBAC/identidade, criptografia de dados, assinatura externa, integridade temporal, auditoria de acesso nem isolamento de processo. Uma pessoa com controle completo de SQLite poderia adulterar todos os campos, inclusive o escopo, de modo que proteção externa e armazenamento confiável permanecem necessários.

## Testes exigidos

- RED/green dos **11 novos cenários**, sem waiver: 3 eixos owner/tenant/workspace × `get` e `list`, leitura com filtro, objeto estrangeiro legítimo, baseline limpo, invariância da base após leitura, `claim_next` sem ação indevida.
- Regressão dedicada: 44 cenários de recuperação real do Outbox após rollback, 8 de restore claim, 64 A79 causal denial, 14 de Twilio/producer hardstop; **141 métodos por SO**, 282 execuções se Windows+Ubuntu passarem.
- Quality canônica 588 módulos/6.895 testes **sem excluir/alterar** as 85 falhas históricas (51 FAIL/34 ERROR); Security A74 365 e H0 A79 64. O resultado do workflow só pode ser declarado após rodar no HEAD exato.
- Nenhuma correção de teste original por `skip`, `xfail`, bypass de produtor, adapter fixture ou ativação Worker.

**HARD NO-GO · ZERO_AUTO_RESEND · Worker OFF · 0/6 P0 homologados · nenhuma PR mesclada, deploy, efeito externo ou custo adicional.**
