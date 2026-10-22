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
