# A306 — Dossiê de reconciliação manual para ACK desconhecido (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · P0 homologadas: 0/6 · custo novo: R$ 0.**

## Objetivo

A305 provou em um `SQLiteChatStore` descartável que o COMMIT pode persistir uma mensagem sem que o cliente receba a confirmação; um banco trasladado isoladamente pode reaparecer HEALTHY sem seu marcador de ACK incerto. A304/A305 também mostraram recibos assinados de revogação após reinício, com assinaturas **sintéticas** e sem custódia independente.

A306 estabelece um **dossiê de revisão humana, exclusivamente de LAB**, que cruza:
- Observação SQLite da A305, obtida de uma mensagem sintética realmente gravada;
- Status antes e depois da reinicialização avaliados novamente pela A305 em modo `READ_ONLY_REVIEW`;
- Identificador semântico estável da intenção e da mensagem;
- Identificador do caso, geração e incidente reaberto, com vínculo ao hash do caso anterior;
- Relator e revisor **declarados**, sem autenticação real de identidade;
- Alegações sobre efeito presente, ausente ou desconhecido, com fonte, referência e hash (dados não autenticados);
- Decisão humana de documentação apenas: `HOLD` ou `ESCALATE`.

## Classificação explícita

1. `LOCAL_EFFECT_OBSERVED_ACK_UNKNOWN`: o SQLite temporário tem a mensagem, mas o ACK original é desconhecido. **Não significa prova de efeito externo nem autorização de reenvio.**
2. `CONFLICTING_CLAIMS`: uma alegação de ausência diverge da observação local ou fontes alegam PRESENT e ABSENT simultaneamente. **Não selecionar maioria, não repetir.**
3. `UNDETERMINED`: falta a observação local ou não há prova suficiente. **Ausência da linha SQLite não prova que uma ação externa nunca aconteceu.**

O avaliador também reconhece cópias repetidas de um recibo, múltiplas alegações da mesma fonte, falta de campos, digest malformado, troca da intenção, caso antigo, geração de incidente divergente, identidade repetida de relator/revisor e decisões `RESEND` ou `RESUME` como impróprias no LAB.

## Invariantes imutáveis

- `can_resume=False`, `can_resend=False`, `can_auto_retry=False`, `can_authorize_real_effect=False`;
- `zero_auto_resend=True`, `automatic_retries=0`, `hard_no_go=True`, `p0_homologated=0`;
- Nenhuma ação de banco, Worker, deploy, provedores ou ordens é disparada pelo dossiê;
- `case_file_locally_valid=True` indica somente consistência **de formato**, não que um revisor real autenticou a decisão;
- `case_digest_sha256` é um hash **local autoatestado**, não uma assinatura independente nem custódia imutável;
- Mesmo que haja duas alegações com nomes diferentes e hashes corretos, sem validação real de origem elas são apenas **alegações**.

## Validação

Testes no Ubuntu e no Windows, Python 3.12, somente dados temporários e biblioteca open-source. 29 testes novos da A306 mais regressões A305–A292. As assinaturas Ed25519 anteriores continuam sintéticas. Não há recuperação de um incidente real nem atestado de hardware/identidade.

## Requisitos reais ainda pendentes

Para encerrar as P0, precisaremos de identidade/autorização independente, recibos externos autênticos, registro monotônico durável, controle comprovado de idempotência por intenção e acesso SQLite autenticado. Não se deve transformar a ficha de revisão em um comando de reexecução — nem mesmo com duas assinaturas locais.

Nenhum merge, pagamento, implantação ou operação real autorizado. **O dossiê documenta a incerteza; não a elimina.**
