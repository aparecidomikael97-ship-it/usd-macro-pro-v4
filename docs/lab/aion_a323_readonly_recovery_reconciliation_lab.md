# A323 — Reconciliação de recuperação somente leitura, nunca liberação (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem merge, Worker, deploy, ordem, provedor ou custo.**

## Base

A322 (#1774) validou a consistência matemática de cópias declaradas da primeira impressão digital da raiz. A321 (#1773) validou duas assinaturas sintéticas por checkpoint e rejeitou forks e rollback quando as duas versões são apresentadas. **Nenhuma dessas etapas estabeleceu custodiantes externos reais, nem uma cabeça antirollback efetivamente retida fora do host.**

A323 cruza os dois contratos com o estado realmente observado de um SQLite descartável em **modo leitura**. Não altera o AION operacional.

## Verificador

Arquivo: `labs/a323_readonly_recovery_reconciliation_lab.py`.

A função `verify_recovery_hold` exige:
1. Pacote de gênese A322 completo, com manifesto canônico, cartão de SHA-256 e duas cópias declaradas. Reexecuta o verificador A322, em vez de confiar numa mensagem de sucesso.
2. Pacote de histórico A321 com cerimônia, duas assinaturas por etapa, baseline, desafios, relógio declarado e informações de revogação. Reexecuta o verificador A321, que por sua vez verifica A320/A319. Exige que o manifesto histórico anterior tenha **o mesmo digest canônico** do manifesto A322.
3. Um único registro local de estado em SQLite real **sintético**, somente num diretório `a323-lab-*`, com marcador `.a323-synthetic-only` e nome fixo `a323-synthetic.sqlite`. Abre com `mode=ro` e `PRAGMA query_only=ON`, sem criar tabelas, modificar dados, restaurar nem reabrir processos operacionais.
4. Comparação dos cinco campos locais com o **último checkpoint assinado**: geração da raiz, época do incidente, sequência, head SHA-256 e digest da intenção. A sequência atrasada ou adiantada e qualquer divergência são recusadas.
5. Operação permitida **somente `OBSERVE_ONLY`**. Um incidente declarado reaberto congela a avaliação; pedidos de RESTORE, RESEND, RESTART_WORKER ou DEPLOY são proibidos antes da leitura.

Resultados:
- `LAB_RECOVERY_CONSISTENT_HOLD_NO_EXTERNAL_AUTHORITY`: todas as **provas controladas pelo laboratório** são coerentes, mas `recovery_authorized=False`, `can_resume=False`, `can_resend=False`, `can_recover_or_restore=False` e `hard_no_go=True`.
- `LAB_RECOVERY_MISSING_EVIDENCE`: pacote ausente, banco não autorizado, estado inexistente/ambíguo ou leitura impossível.
- `LAB_RECOVERY_CONFLICT_VETO`: cabeça local atrasada, adiantada, incompatível com as testemunhas, manifesto de origem diferente ou histórico assinado inválido.
- `LAB_RECOVERY_DENIED`: pedido operacional ou incidente reaberto.

Todas as respostas mantêm **0/6 P0 homologadas, ZERO_AUTO_RESEND e zero tentativa automática**. Nenhum resultado autoriza reenvio, abertura de Worker, instalação de serviço, novo custo ou operação com provedor.

## Contraprovas e limites de confiança

Uma verificação somente local não consegue provar que os recibos A322/A321 foram realmente guardados por pessoas/serviços independentes. O teste adversarial modifica o high-water inicial, recria o manifesto A319/A320, assina outra cadeia A321, reemite o cartão A322 e também substitui o SQLite sintético. O verificador encontra **coerência matemática** e continua recusando recuperação. Esta contraprova demonstra que a A323 **não fecha** P0-3 nem P0-4.

Se um atacante ocultar o checkpoint mais recente e apresentar uma cadeia inteira válida anterior, um verificador sem **high-water externo previamente autenticado** não pode perceber a substituição. Também não existem ACK de provedor, reserva de efeito semântico, relógio independente, controle operacional de chaves, verificação nativa SQLite WAL/SHM ou custódia imutável. Não homologar nenhuma P0.

## Bateria

`python -m unittest -v labs.test_a323_readonly_recovery_reconciliation_lab`

33 testes A323 com SQLite nativo descartável e assinaturas Ed25519 sintéticas, mais regressões A322/A321/A320/A319/A318/A317/A316/A315/A314/A313/A312/A311/A310/A309/A246/A247/A292/A293/A299 no Ubuntu e Windows.

**Próxima etapa útil:** antes de tratar recuperação como operacional, estabelecer e autenticar um high-water externo realmente independente, sua política de não-apagabilidade e seu vínculo com a intenção e o ACK do provedor. A323 não cria ou contrata esse serviço.
