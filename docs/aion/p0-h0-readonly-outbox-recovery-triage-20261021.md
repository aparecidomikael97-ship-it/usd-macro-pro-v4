# AtlasQuant / AION P0 H0 — recuperação após resultado incerto sem reenvio

**21/10/2026 · LAB isolado · HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND**

## Decisão técnica

O problema de H0 não é somente validar mais assinaturas sintéticas. É a **perda de conhecimento causal** entre o primeiro envio potencialmente executado pelo fornecedor e a persistência local. Após interrupção, SQLite pode conter `PENDING`, `CLAIMED` ou nem sequer conter a intenção, apesar de o fornecedor ter recebido a operação. Um `404`, uma lista incompleta, um token de idempotência alegado ou `COMMITTED_EFFECT` assinado sob chaves fornecidas pelo próprio executor não comprovam a inexistência de efeito.

A opção segura, enquanto não houver independência real comprovada, é **não permitir reenvio, reconstrução automática nem fechamento terminal**, e exigir investigação humana com recibo originado do produtor quando tecnicamente disponível.

## Entrega técnica desta rodada

O módulo `atlasquant_aion_p0_h0_recovery_triage_readonly_lab.py` examina **dados da classe real `ExecutionOutbox`**, diferentemente dos módulos anteriores de cinco e sete assinaturas sintéticas. A única chamada por ID é `outbox.get(idempotency_key)`, de leitura local; **não chama** `enqueue`, `claim_next`, `dispatch_claimed`, `reconcile`, `compensate`, métodos de adapter ou quaisquer endpoints. Não integra o Worker e não grava eventos.

A entrada é um manifesto estrito de **pistas históricas fornecidas pelo chamador**: chaves de intenção já observadas, último estado, número de tentativas e início de despacho. Não se autentica o manifesto, que pode ser inventado ou restaurado junto com SQLite. O módulo compara cada pista com o estado local atual e produz **apenas observações**, bloqueios fixos e motivo para revisão manual. Não inclui payload da ação, dados de terceiros, chaves privadas ou tokens de autorização no resultado.

| Situação local observada | Classificação de triagem | Permissão |
| --- | --- | --- |
| Intenção desapareceu do DB | `MISSING_LOCAL_INTENT_NOT_EVIDENCE_OF_NO_EFFECT` | Negada |
| Intenção voltou a `PENDING` após `SENT/UNCERTAIN` previamente alegado | `POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM` | Negada |
| Número de tentativas ou despacho regrediu | `POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM` | Negada |
| `SENT` ou `UNCERTAIN` | `UNKNOWN_EXTERNAL_EFFECT_REQUIRES_PROVIDER_RECONCILIATION` | Negada |
| `CONFIRMED` gravado localmente | `LOCAL_CONFIRMED_NOT_EXTERNAL_PRODUCER_AUTHENTICATION` | Negada |
| `BLOCKED_PRODUCER` | `UNENROLLED_PRODUCER_REMAINS_BLOCKED` | Negada |
| Histórico SQLite indisponível ou malformado | `LOCAL_HISTORY_UNAVAILABLE_OR_CORRUPT` | Negada |
| Registro local parece consistente | `LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY` | Negada |

Qualquer entrada: **`state=HARD_NO_GO`**, `reconciliation_state=UNKNOWN_BLOCKED`, `allowed=False` e 14 indicadores de capacidade/autorização `False`. O módulo não é nem pretende ser uma autorização para operação manual; apenas uma fila de evidências a investigar.

## Teste de restauração do SQLite real

A bateria `tests/test_aion_p0_h0_recovery_triage_readonly_lab.py` cria bancos SQLite descartáveis com `SQLiteChatStore` e `ExecutionOutbox` reais, registra intenção e simula os seguintes cenários de degradação:

1. Snapshot após enfileiramento, antes de `UNCERTAIN`; restauração para `PENDING`. Com pista posterior a `UNCERTAIN`, a triagem aponta possível regressão, mas não executa nenhuma ação.
2. Snapshot **antes do primeiro enfileiramento**; restauração perde completamente o registro de intenção. A triagem aponta **intenção desaparecida**, que não prova ausência de efeito externo.
3. Snapshot do SQLite e manifesto de pistas **restaurados juntos**. A triagem não consegue perceber a regressão: o estado `PENDING` parece coerente. Este é um **contraexemplo ainda aberto**, e o retorno continua HARD NO-GO.
4. Despacho com horário ou contador conhecido que desapareceu após rollback; classificado como suspeito.
5. Estados locais `UNKNOWN/SENT/CONFIRMED/BLOCKED_PRODUCER/RETRY`, dados e timestamps hostis, keys SHA-256 malformadas, DB fechado/corrompido, duplicações de pistas.
6. `tuple(db.iterdump())` antes/depois para demonstrar que a inspeção não alterou a base; `effect_count()==0` nas fixtures.

**44 testes novos** e regressão dos 407 métodos de LAB anteriores: **451 por SO / 902 execuções selecionadas** caso Windows/Ubuntu passem. O único significado de PASS é que o comportamento restritivo esperado foi reproduzido. Não transforma a triagem em fonte de verdade independente.

## Critérios de fornecedor — evidência necessária, não presumida

Para cada API real candidata, registrar evidência oficial atualizada e testável de:

- Identificador de tentativa enviado junto com a chamada e **persistido pelo fornecedor**, com unicidade por escopo, inclusive após falha de rede.
- Contrato documental e teste sobre **deduplicação/idempotência real**; informar retenção, timeout, concorrência, reaplicação e mudança de payload.
- Forma comprovável de fazer readback **exaustivo e causal** por tentativa, com prova de versão mais recente, e como distinguir registros ainda em processamento.
- Capacidade comprovável de **fencing de ausência de efeito**, garantindo que a operação original não aparecerá mais depois do no-effect. Um `404`, ausência em listagem, cancelamento agendado ou afirmação sem fonte **não basta**.
- Controle independente de conta, administração, chave, recovery/MFA, retenção e revogação, fora do computador que executa o AION.
- Procedimento de reconciliação humana quando a API não oferece as propriedades necessárias. **Não transformar limitações da API em simulação de uma garantia ausente.**

### Política de falha

Se uma API não suportar idempotência forte/fence comprovado, o caminho seguro será **bloquear a repetição automática** e fazer reconciliação supervisionada, ou optar por outro fornecedor/protocolo antes da operação real. Nunca assumir `NO_EFFECT_FENCED` por silêncio do fornecedor.

## Pendências sem dispensa

- Fonte externa indep. que sobreviva à restauração conjunta do host e do próprio registro de pistas.
- Registro de primeira tentativa e consumo de nonce atomicamente **fora** do executor.
- Identidade do fornecedor e authenticidade dos recibos, latest/head readback verificável.
- HUMAN_OWNER validado com aprovação real; recuperação física, rotação e revogação.
- **Quality canônica histórica RED: 52 FAIL + 34 ERROR**, 0/6 P0 homologados.
- Sem ativar Worker, sem merge/deploy, sem gastos adicionais, sem confirmar eficácia em ambiente real.

**Regra:** a capacidade de *detectar um indício de rollback* é diferente de *impedir efeito repetido após rollback*. Este LAB caracteriza o primeiro aspecto em alguns cenários. O segundo só pode ser homologado com um domínio externo verdadeiramente independente e teste de integração autorizado.
