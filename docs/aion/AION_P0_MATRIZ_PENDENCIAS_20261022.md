# AION — MATRIZ DOS SEIS P0 (22/10/2026, após A175)
**Controle de pendências; não é certificado de prontidão. 0/6 homologados, HARD NO-GO.**

| P0 | Bloqueio | Evidência LAB atual | Falta para aceite verificável | Próxima ação autorizada |
|---|---|---|---|---|
| 1 — Identidade proprietário | Autoafirmação não prova HUMAN_OWNER real | contratos e assinaturas sintéticas A165/A166 | prova de controle de chave do proprietário + verificação independente de identidade/cerimônia + revogação | especificar cerimônia e ensaio de chaves perdidas; sem identidade real, NO-GO |
| 2 — Recibos | Assinaturas auto-fornecidas não autenticam produtor/efeito | contratos A165/A166, limites A167 | recibo **assinado por fonte externa confiável**, vinculando ID/efeito, relógio e chave válida; consultas/revogação | coletar requisitos públicos de provedor; não contratar nem criar credenciais |
| 3 — Primeira intenção incerta | reenvio após crash/rollback ou ID novo | A173 preserva outcome UNKNOWN em uma fachada; A174 reserva local; A175 deduplicação de efeito declarado | vínculo com efeito verdadeiro, bloqueio persistente após host restaurado e prova independente de estado; nenhuma passagem UNKNOWN→RETRY | caracterizar rota de retentativa real; ensaiar ID forjado, rollback e recriação de diário |
| 4 — H0 após reinício | evidência local apagada/host reiniciado pode conceder nova tentativa | A174/175 reinício normal com diário presente; deleção continua bypass | testemunha monotônica independente e teste em infraestrutura-alvo, ausência de testemunha deve bloquear operações | ensaiar desaparecimento de diário e indisponibilidade de testemunha, registrar fail-closed |
| 5 — SQLite leitura | identidade nativa/VFS não atômica, ABA e falsos positivos | A168–A172 ensaios Windows/Ubuntu | vínculo comprovável com handle realmente usado ou substituição de arquitetura, teste hostil cross-platform e compatibilidade | testes adversariais da leitura sem falsa homologação |
| 6 — SQLite escrita | pós-commit incerto/ABA, leitura do mesmo caminho não atesta FD SQLite | A173 marcou UNKNOWN pós-commit em Ubuntu e manteve ZERO_AUTO_RESEND | reconciliação robusta, vínculo de identidade, caminhos backup/restore, recuperação de falha real | inventário de call sites e métodos fora da proteção (p.ex. backup_to), testar sem efeitos externos |

## Ordem de fechamento, sem deixar pendências ocultas
1. **P0-3 interno:** identificar o ponto de chamada que decide a retentativa e estabelecer invariantes `UNKNOWN=>NO_RETRY` inclusive em exceções inesperadas. A175 **não foi conectado** ao Worker/fachada operacional.
2. **P0-3/4 interno:** demonstrar por testes a ausência de segurança contra deleção/restauração de diário e identidade forjada; exigir contrato externo, sem presumir que SQLite ou marcador local sejam testemunhas independentes.
3. **P0-5/6 interno:** reduzir falsos positivos e caracterizar identidade de arquivo realmente aberto, concorrência e backup; testes isolados por OS.
4. **P0-1/2/4 externo:** somente evidência independente pode homologar identidade, recibo e estado monotônico/recuperação real.
5. **Gate final:** CI LAB e Quality canônica auditados, cenários adversariais sem falha crítica, demonstração de recuperação de primeira intenção, quórum externo válido, validação humana. Só após isso avaliar merge/deploy/Worker separadamente.

### Evidência e escopo
- A174: [PR #1464](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1464), 170 execuções LAB.
- A175: [PR #1465](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1465), [CI #39865960416](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39865960416), 93/93 Ubuntu e 93/93 Windows.
- Mesmo efeito declarado sob novo request_id: negado. **Novo business_id falso e deleção de diário: ainda aceitos no LAB**.
- Não se verificaram a Quality canônica completa, provedores externos, hardware resistente a rollback ou identidade de proprietário real nesta rodada.
- **Proibido:** declarar P0 fechado, reativar Worker, integração com cliente real, merge ou deploy sem homologação; ZERO_AUTO_RESEND.

## Adendo A176 — auditoria do call site Outbox
[PR Draft #1466](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1466), [CI GREEN #39867557973](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39867557973) — Ubuntu 33/33 e Windows 33/33.

**P0-3 — avanço confirmado apenas no LAB:** o Outbox não confia mais em `retryable=True` após enviar, nem em `authoritative_absence=True` do próprio adaptador para liberar `RETRY`. Reproduções RED do comportamento anterior ficaram registradas no CI #39867407275.

**P0-2/P0-3 — pendências explícitas:** declaração de rejeição definitiva (`accepted=False,retryable=False`) ainda permite `FAILED` e não é recibo independente de efeito zero; confirmação `found=True,confirmed=True` ainda é autoafirmada pelo adaptador. Falta proteger contra novo ID de negócio falso, restauração/exclusão do diário e autenticação de provedor. Não houve inspeção completa de todos os call sites. Ver [documento A176](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/lab/aion-p0-outbox-uncertain-retry-gate-a176-20261022/docs/aion/AION_P0_OUTBOX_UNCERTAIN_RETRY_A176_LAB_20261022.md).

**Prioridade seguinte:** teste RED do efeito que ocorre antes de uma falsa rejeição definitiva + recibo falso de confirmação; aplicar fail-closed em LAB sem enfraquecer os testes de saga, depois revisar dependências de testemunha externa. P0 homologados: **0/6**.

## Adendo A177 — contratos de rejeição e confirmação não autenticados
**PR #1467:** [RED #39868471657](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39868471657) com 3 divergências de estado e 4 erros de API por SO. [GREEN #39868617571](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39868617571) 40/40 Ubuntu + 40/40 Windows; regressão [A176 #39868617589](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39868617589) 33/33 Ubuntu + 33/33 Windows. **146 execuções**, Quality canônica não rodada.

- **P0-3 parcial LAB:** rejeição supostamente definitiva depois de send não se torna `FAILED` sem confirmação de ausência de efeito. Indefinição continua `UNCERTAIN`; nenhuma liberação para `RETRY`.
- **P0-2 parcial LAB:** confirmação declarada pelo próprio adaptador não vira ledger `CONFIRMED` sem um verificador. Sem verificador, ausente/falhando, bloqueia.
- **P0-2 bloqueio externo:** o callback `evidence_verifier` é injetável e verificadores dos testes são sintéticos, não identificam fonte de recibos confiável. Requer pinagem de chaves públicas externas, política de raiz de confiança, assinatura verificável, revogação e proveniência independente.
- **P0-3/4 pendentes:** diário local apagável/restaurável, negócio falso com ID novo, recuperação H0 sem testemunha monotônica, ausência de cobertura de toda a rota operacional.
- **P0-5/6 pendentes:** identidade nativa de arquivo SQLite e restauração atômica não atestadas.
- Documento auditável: [A177](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/lab/aion-p0-outbox-proof-admission-a177-20261022/docs/aion/AION_P0_OUTBOX_RECEIPT_ADMISSION_A177_LAB_20261022.md). **P0 homologados 0/6, HARD NO-GO.**

## Adendo A178 — prova de assinatura Ed25519, mas sem autenticidade externa
A [PR Draft #1468](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1468) adiciona verificador Ed25519 **somente LAB** e 16 testes adversariais. [CI A178 #39869577629](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39869577629): 56/56 Ubuntu e 56/56 Windows; [SQLite #39869577563](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39869577563): 93/93 Ubuntu e 93/93 Windows. **298 execuções**, Quality completa não rodou.

- **P0-2 progresso LAB:** assinatura, escopo, digest completo da intenção, issuer/key ID, effect_ref, nonce, seq, validade e revogação de teste verificados; chave desconhecida, conteúdo alterado e replay cruzado são negados nos testes.
- **P0-2 bloqueio crítico:** quem define a lista de chaves pode fixar a própria chave e aprovar recibo inventado. `A178_CALLER_CONTROLS_TRUST_ROOT=FAKE_PROOF_ACCEPTED_NOT_EXTERNAL`. Requer proveniência independente das chaves, custódia e recibos emitidos por fonte confiável real.
- **P0-3/4 bloqueio crítico:** restaurar instantâneo antigo do contador high-water permite aceitar recibo velho. `A178_ROLLBACK_OF_TRUST_SNAPSHOT=REPLAY_ACCEPTED_NOT_ATTESTED`. Requer prova externa monotônica, anti-rollback e recuperação física.
- **P0-1 permanece:** identidade HUMAN_OWNER real não validada; testes de chave LAB não comprovam pessoa ou controle independente.
- **P0-5/6 permanecem:** nenhuma vinculação atômica ao descritor VFS do SQLite nem homologação em host adversarial.
- [Evidências, contrato e contraprovas A178](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/lab/aion-p0-ed25519-receipt-a178-20261022/docs/aion/AION_P0_PINNED_ED25519_RECEIPT_A178_LAB_20261022.md).

**Próxima prioridade:** pinagem de fonte de confiança fora do adapter + teste de falha/rollback de testemunha, sem passar para produção. P0 homologados: **0/6**.

## Adendo A179 — testemunha assinada em desafio, sem custódia real
[PR #1469](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1469), [CI A179 #39870396609](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39870396609) = **77/77 Ubuntu e 77/77 Windows**; [SQLite #39870396346](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39870396346) = **93/93 Ubuntu e 93/93 Windows**. **340 execuções em LAB**, Quality canônica ainda não reexecutada.

- **P0-2 avanço somente LAB:** segunda assinatura Ed25519 verificada sob chave separada, challenge aleatório de 256 bits, digest da confiança do fornecedor, vínculo com recibo/decisão/efeito, recusa se testemunha indisponível, revogada, expirada ou assinatura inválida. Fonte da chave continua auto-configurável e não autenticada externamente.
- **P0-3 avanço somente LAB:** A177 fail-closed não altera UNKNOWN/SENT sem dupla verificação sintética. Uma RESERVA DA PRIMEIRA INTENÇÃO ANTES DO SEND ainda NÃO foi comprovada. O witness A179 é de admissão de recibo, não de autorização durável pré-envio.
- **P0-4 pendência fundamental:** `A179_WITNESS_STATE_ROLLBACK=REPLAY_ACCEPTED_NOT_ATTESTED`. Retomar uma testemunha restaurada e assinando corretamente reabre uma evidência já consumida. Quórum/custódia independente resistente a rollback não existe.
- **P0-1/P0-2:** `A179_CALLER_REPINS_WITNESS_ROOT=FAKE_AUTHORITY_ACCEPTED`. Se chamador controla a chave que o verificador supõe confiável, pode simular uma autoridade de testemunha. Falta bootstrap independente de chaves, autenticação do titular, política de revogação e proveniência do fornecedor.
- **P0-5/P0-6:** banco SQLite e VFS continuam sem prova atômica do arquivo nativo; os 93/93 de regressão não homologam compatibilidade hostil.
- [A179 contrato e provas](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/lab/aion-p0-witness-admission-a179-20261022/docs/aion/AION_P0_WITNESSED_RECEIPT_A179_LAB_20261022.md).

**Próximo gate obrigatório:** especificar e demonstrar autoridade independente de primeira reserva, high-water irreversível, continuidade H0 após host e testemunha restaurados, procedência de chaves e recibos emitidos por provedor real. Não substituir esse gate por mais hashes/assinaturas sintéticos. **P0 0/6, HARD NO-GO, ZERO_AUTO_RESEND.**

## Adendo A180 — reserva antes de enviar (P0-3)
[PR Draft #1470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1470) · [CI A180 #39871528923](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528923): **95/95 Ubuntu + 95/95 Windows** · [SQLite #39871528959](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39871528959): **93/93 Ubuntu + 93/93 Windows**. Total 376 execuções específicas e herdadas; outros workflows A176–A179 repetidos com sucesso. Quality completa pendente.

**Red → green verificável:** `ExecutionOutbox.dispatch_claimed` agora registra `UNCERTAIN` de forma durável antes de contactar qualquer testemunha de primeira tentativa e só chama `adapter.send` após um callback de reserva verificado. Sem testemunha, com resposta perdida ou assinatura inválida, nenhum envio acontece; reinício e expiração de lease não autorizam reenvio. Testes anteriores receberam callbacks de **LAB explicitamente sintéticos**, não certificados. Os 18 cenários A180 incluem ID técnico novo com mesmos dados semânticos e recuperação após reserva incerta.

**Pendências P0-3/4 essenciais:**
- `A180_RESTORED_WITNESS=REPEATED_SEMANTIC_EFFECT_NOT_ATTESTED`: rollback da própria testemunha admite novamente a mesma operação declarada.
- `A180_CALLER_REPINS_FIRST_WITNESS=FALSE_AUTHORITY_ACCEPTED`: se o hospedeiro pode fixar outra chave, prova autoassinada é admitida. O callback ainda é injetável por qualquer chamador capaz de construir o Outbox.
- `A180_ALTERED_SEMANTIC_DESCRIPTOR=UNDETECTABLE_AS_SAME_EFFECT`: o hash semântico de ação/escopo/alvo/payload não é prova externa de identidade do efeito e pode tanto falhar em reconhecer um efeito quanto bloquear dois eventos legítimos idênticos.
- Não há guarda operacional obrigatória para todos os serviços, custódia independente resistente a rollback, atestado real de reserva antes de efeito, testemunha pós-falha H0, rastreio nativo do SQLite nem procedência de chaves.
- Ver [evidências e contratos A180](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/lab/aion-p0-preflight-witness-a180-20261022/docs/aion/AION_P0_FIRST_ATTEMPT_WITNESS_A180_LAB_20261022.md). **P0 0/6, HARD NO-GO, ZERO_AUTO_RESEND.**

**Próximo gate recomendado:** definir requisitos de serviço externo que ofereça reserva durável *antes* da fronteira, idempotência de evento de negócio autêntico, identidade de chaves comprovada, consulta independente H0 e garantia explícita contra rollback do próprio custódio. Uma simulação local extra não fechará esse P0.

## Adendo A181 — perda/restauração do diário do host versus custódia simulada
[PR Draft #1471](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1471). [CI A181 #39872947467](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39872947467) = **110/110 Ubuntu + 110/110 Windows**; [SQLite #39872947397](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39872947397) = **93/93 Ubuntu + 93/93 Windows**, 406 execuções de regressão LAB. Primeira tentativa em Windows revelou handle SQLite aberto em arquivo corrompido; correção em `_connect` foi repetida em ambos os SOs.

- **P0-3 (LAB):** comprovada a cadeia `reservar e persistir no segundo arquivo → assinar → permitir apenas primeira tentativa`. Ao perder/restaurar o SQLite do AION, uma custódia **preservada** reconhece o mesmo efeito declarado mesmo com novo `request_id` e mantém `ZERO_AUTO_RESEND`. COMMIT da reserva com ACK perdido bloqueia sem enviar. O hash semântico não autentica evento de negócio; duas operações legítimas idênticas podem ser incorretamente negadas.
- **P0-4 (LAB):** o segundo arquivo persiste após perder o primeiro; **não** existe disponibilidade H0 externa verificada, proteção contra queda de máquina/custódio físico ou bootstrap independente. A testemunha continua vulnerável a restauração e a re-inicialização explícita após perda total.
- **P0-1 e P0-2:** chaves e signatários são sintéticos e auto-configuráveis. `A181_INJECTED_TRUE_GUARD=FAKE_AUTHORITY_ACCEPTED` comprova que o callback injetável não é fronteira de confiança de produção; faltam identidades/autorização autênticas e chaves externas provisionadas.
- **P0-5/P0-6:** um novo teste detectou vazamento de conexão sob corrupção SQLite no Windows; corrigido em LAB. Ciclo de vida da SQLite passou regressões, mas identidade VFS/FD e preservação anti-rollback não estão homologadas.
- **Contraprovas prioritárias A181:** `CUSTODY_REENROLL_AFTER_WIPE` e `CUSTODY_SNAPSHOT_ROLLBACK` autorizam novamente uma intenção que já havia sido reservada. Ambos os bancos residem no mesmo CI, logo nenhuma independência física foi demonstrada.
- [Relatório e critérios A181](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/lab/aion-p0-external-custody-recovery-a181-20261022/docs/aion/AION_P0_TWO_FILE_CUSTODY_A181_LAB_20261022.md).

**Próximo gate não substituível por LAB:** fonte de confiança externa com chave registrada de modo independente, contador durável resistente a rollback/restauração, identidade imutável de evento de negócio, política de reconstrução de gênese, testemunha disponível fora do host e ensaio H0 real. Quality completa ainda pendente. **0/6 P0 homologados, HARD NO-GO, sem merge/deploy/Worker.**


## Adendo A182 — vínculo original e checkpoints locais, sem independência externa
Ramo LAB `lab/aion-p0-intent-binding-a182-20261022`, baseado no head A181 `e58fd2b073f4eddb46d406da9b62e85bbe350aca`. Ver [relatório A182](AION_P0_INTENT_BINDING_A182_LAB_20261022.md).

| P0 | Evidência/limite A182 | Status |
|---|---|---|
| 1 | original local não autentica proprietário/identidade de negócio; substituição da inscrição continua aceitando | ABERTO |
| 2 | assinatura e fingerprint fixo rejeitam alteração unilateral; substituir raiz junto ao fingerprint continua aceitando autoridade falsa | ABERTO |
| 3 | guard LAB opt-in vincula candidato à intenção original canônica, rejeita alterações e preserva ZERO_AUTO_RESEND; não cobre chamador privilegiado/reinscrição | ABERTO |
| 4 | checkpoint retido detecta custódia abaixo do ordinal; rollback conjunto/rebootstrap com checkpoint antigo continua replay | ABERTO |
| 5 | regressão SQLite executada; vínculo nativo/VFS e identidade atômica continuam não provados | ABERTO |
| 6 | sem alteração ao armazenamento operacional; rollback/backup e vínculo ao handle nativo continuam sem homologação | ABERTO |

Local: 132/132 regressões (22 A182, incluindo sete caracterizações de risco); SQLite 92 PASS + 1 ERROR por dependência requests ausente/proxy indisponível. Requisitos externos em suíte separada: **3 FAIL reais**, sem supressão. CI Ubuntu/Windows configurado com jobs externos deliberadamente vermelhos; detalhes de runs/logs devem ser conferidos no relatório/adendo de validação. Quality canônica não executada. Nenhum P0 fechado, **0/6 homologados, HARD NO-GO**.

