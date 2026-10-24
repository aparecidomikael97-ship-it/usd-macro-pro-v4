# A190 G9 — ADR LAB: primeira tentativa, ACK do fornecedor e reconciliação autenticada

**Checkpoint local:** 2026-10-23 (America/Manaus). **Base:** G8 Draft #1495; missão A190 #1486. **HARD NO-GO** e seis P0 não homologados.

## Objetivo

G7/G8 demonstraram que reserva local e assinatura do custodiante não são prova de efeito do fornecedor; podem ser repetidas após rollback administrativo. A lacuna seguinte é distinguir a **reserva da tentativa** do **resultado de uma integração externa** e lidar com ACK perdido, sem assumir que tempo esgotado significa que nada aconteceu.

**G9 implementa apenas contratos simulados**. Nenhuma API de fornecedor, conta, cliente, operação financeira, segredo operacional, destino externo ou Worker foi usada.

## Papéis (todos sintéticos e no MESMO runner/host)

1. **Origem do evento:** chave Ed25519 aleatória G8 assina a semântica de evento sem efeito. Sem identidade de origem certificada.
2. **Custodiante da reserva G8:** verifica assinatura original, impede múltiplos requests para mesmo digest enquanto SQLite íntegro e assina recibo RESERVED_ONLY.
3. **Cliente de primeira tentativa G9:** grava journal SQLite antes de qualquer envio sintético; tenta uma vez; erro/timeout/reinício implica UNCERTAIN e impede reenvio automático.
4. **Fornecedor simulado G9:** processo TCP separado com chave Ed25519 própria, ledger SQLite de unicidade semântica e comprovante SIMULATED_RECORD_NOT_EXTERNAL_EFFECT, nunca recibo de provedor real.
5. **Reconciliador G9:** consulta SOMENTE LEITURA e valida pin fixo do fornecedor sintético mais o vínculo ao recibo de reserva. Não autoriza uma nova tentativa, nem comprova efeito real.

## Transições e invariantes

| Situação | Decisão do ensaio | Regra que precisa sobreviver em produção |
| --- | --- | --- |
| Reserva assinada pelo custodiante; primeira tentativa não gravada | Nenhuma alegação de efeito | Sem prova de autorização ainda |
| Journal de tentativa confirmado; processo morre antes de enviar | UNCERTAIN, zero auto resend; lookup NOT_FOUND continua incerto | Não converter silêncio do provedor em licença para reenviar |
| Fornecedor simulado grava SQLite e perde resposta TCP | UNCERTAIN, zero auto resend | Consultar histórico do fornecedor; diferenciar reserva de execução |
| Consulta read-only obtém recibo com pin/vendor distinto + vínculo ao hash de reserva | SIMULATED_VENDOR_RECORD_RECONCILED_READ_ONLY | Prova real exigiria recibo real com identidade, chave e semântica assinadas independentemente |
| Vendor/autoridade indisponível H0 | Sem efeito novo; UNCERTAIN | Fail closed, offline read-only rotulada |
| Cliente altera request ID, journal some ou concorrência 6 requisições | Ledger sintético íntegro nega segunda operação; 1 registro | Depender da idempotência verificável do fornecedor real |
| Admin restaura SQLite do próprio fornecedor sintético | Nova assinatura/registro aceito (**RED**) | Verdadeiro domínio externo deve reter unicidade contra rollback do cliente/host |
| Cliente cria assinatura falsa, pin falso, estado REAL_PROVIDER_PAID, epoch/tempo errado | Rejeitado sob pin esperado | Requisitos de raiz externa, revogação e proveniência ainda faltantes |

## Conquistas limitadas do laboratório

- Duas assinaturas criptográficas distintas para etapas distintas, com separação de domínios.
- Testes cross-platform com subprocessos e socket real 127.0.0.1, SQLite/synchronous=FULL e commit anterior ao fechamento TCP do ACK perdido.
- Correlação explícita via SHA256 canônico do recibo de reserva; recibo de outra intenção não serve para confirmar a primeira.
- Ledger sintético do fornecedor recusa um segundo request_id enquanto íntegro.
- Testes incluem restauração do histórico do próprio fornecedor sob admin/root: **contraexemplo RED** necessário para evitar falsa conclusão de independência.

## P0 que seguem sem evidência suficiente

- HUMAN_OWNER e autenticação de emissor original fora da infraestrutura AION; autorizações, FIDO2/Windows Hello, revogação e vínculo a ação/tenant.
- Origem/provedores externos reais, âncoras publicadas fora do controle local e assinaturas sob chaves cuja custódia seja independente.
- Contrato verdadeiro de idempotência e reconciliação de efeitos externos; o vendor aqui é software nosso.
- Resistência a root/admin, restauração conjunta, backups, H0 após power loss, clock drift, quorum, downgrade de pin e disponibilidade externa.
- Cinco external-RED por OS, 43 advisories herdados, testes Quality/Security canônicos e a homologação formal dos seis P0.

## Decisão

O próximo passo válido não é chamar o software sintético de fornecedor. É buscar **prova de contrato e custódia de terceiro independente**, com documentação primária, owner approval e análise FinOps antes de comprar/ativar. Se a autoridade ou o provedor não estiver disponível, a autorização de novo efeito fica NEGADA, ainda que a interface local funcione.

**Nenhuma contratação ou escolha de fornecedor foi feita**; limite operacional vigente R$200/mês, exceção pontual R$250 apenas com aprovação expressa.

**0/6 P0 — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** PR Draft empilhada sobre #1495, sem merge/main, deploy/Worker ou envio real.
