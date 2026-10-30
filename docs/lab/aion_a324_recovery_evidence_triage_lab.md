# A324 — Triagem de provas ausentes, atrasadas e contraditórias antes de qualquer recuperação (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem merge, Worker, deploy, ordens, provedor, efeito externo ou custo novo.**

## Contexto

A323 (#1775) passou em Ubuntu e Windows com 453 testes por plataforma e zero falhas inesperadas. Ela reexecuta A322/A321/A320/A319, lê um único estado de um SQLite sintético com `mode=ro` e bloqueia recuperação se o histórico local e o histórico assinado forem diferentes. Todavia o AION ainda não tem testemunhas verdadeiramente externas. A324 cobre um problema novo: **a evidência de duas testemunhas pode nem chegar, chegar tarde ou chegar divergente**, inclusive com COMMIT incerto ou incidente reaberto.

## Contrato implementado

`labs/a324_recovery_evidence_triage_lab.py` implementa `investigate_recovery_evidence`:

- Admite apenas `operation="INVESTIGATE_ONLY"`; pedidos de RESTORE, RESEND, RETRY, RESTART_WORKER, DEPLOY, AUTHORIZE_EFFECT e OBSERVE_ONLY são negados *antes* de consultar SQLite.
- Incidente reaberto produz congelamento processual imediato. Entradas ou relógio declarado malformados também.
- Exige os pacotes completos de gênese A322 e de histórico A321; exige exatamente **dois comprovantes de recebimento declarados**, um por cada identidade de custodiante do último checkpoint assinado.
- Compara o SHA-256 do **checkpoint integral, inclusive assinatura**, e os campos de geração, incidente, sequência, cabeça e intenção. Compara também o digest declarado do envelope de entrega que vincula suposto custodiante, canal e horário.
- Recusa dois comprovantes do mesmo custodiante ou canal, identificador desconhecido, hash/estado contraditório, campos de GO, digest de envelope adulterado e timestamps incoerentes. Compara idade *declarada* (janela fixa 120 segundos) apenas como filtro de segurança sintético: **não é relógio confiável**.
- Quando ambas as declarações estão formalmente íntegras, reexecuta A323, que por sua vez revalida A322/A321/A320/A319 e compara **bytes atuais** do SQLite de laboratório somente em leitura. Divergência local ou fork assinado levam à investigação, não a uma ação.
- Não há fila de reenvio, armazenamento de credenciais, operação de escrita, coleta externa, transação de provedor, desbloqueio, serviço contínuo nem agendamento de retry.

Respostas:

- `LAB_INVESTIGATE_EVIDENCE_HOLD`: falta de prova ou atraso, evidência inválida, histórico irresolúvel ou banco ilegível.
- `LAB_INVESTIGATE_CONFLICT_HOLD`: fontes contraditórias, assinatura/cabeça/intenção incompatíveis, fork ou rollback local.
- `LAB_PROCEDURAL_HOLD`: incidente reaberto, comando operacional solicitado ou parâmetros de controle inválidos.
- `LAB_COHERENT_EVIDENCE_STILL_HOLD`: **somente coerência matemática** dos documentos declarados e do SQLite de teste. Nunca GO.

Todos os retornos contêm `external_custodians_independently_authenticated=False`, `trusted_clock_and_receipt_freshness_proven=False`, `high_water_off_host_immutable_proven=False`, `provider_outcome_verified=False`, `can_resolve_unknown_commit=False`, `can_restore=False`, `can_resend=False`, `can_auto_retry=False`, `automatic_retries=0`, `zero_auto_resend=True`, `hard_no_go=True`, `p0_homologated=0`.

## Contraprova indispensável

No teste adversarial, o mesmo host reduz a sequência histórica original, recria manifesto/cabeça/cerimônia/assinaturas da A319–A321, recria a gênese A322, regrava um **SQLite sintético** e emite dois novos comprovantes de recebimento. As verificações matemáticas aceitam a coerência, mas a A324 conserva HARD NO-GO. A evidência de duas cópias **autodeclaradas** jamais prova independência, chegada real ou imutabilidade.

Uma confirmação de recebimento não é um ACK do provedor. Um COMMIT SQLite incerto não pode ser resolvido pela existência desses comprovantes sintéticos. Se uma testemunha não responder, não solicitar automaticamente um novo envio de efeito; investigar manualmente e preservar a cerca.

## Operacionalização futura (NÃO executada)

A investigação real precisará de identidades e chaves de custodiantes previamente autentificadas fora do host, recibos obtidos por canais independentes, um head antirollback consultado diretamente das testemunhas, uma política de ausência/latência e reconciliação de efeitos com ACK assinado do provedor. O teste não simula esse acesso como se ele já existisse.

## Bateria

`python -m unittest -v labs.test_a324_recovery_evidence_triage_lab`

30 testes novos mais regressões A323/A322/A321/A320/A319/A318/A317/A316/A315/A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299 no GitHub Actions Ubuntu/Windows. Nenhuma alteração em `aion_chat/store.py`, nenhum merge ou contrato operacional liberado.

**Próximo bloqueio real:** custódia realmente independente da cabeça e da primeira raiz, revogação/relógio confiáveis e confirmação de efeitos fora do host antes de qualquer recuperação. P0-3/P0-4 continuam abertas.
