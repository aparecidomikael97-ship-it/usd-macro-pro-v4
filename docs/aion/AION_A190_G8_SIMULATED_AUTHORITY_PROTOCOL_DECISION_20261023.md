# A190 G8 — ADR LAB: contrato de autoridade fora do estado do cliente; sem falsa independência

**Data local:** 2026-10-23 (America/Manaus). **Missão:** #1486. **Base:** G7 Draft #1494. **Decisão:** testar o contrato de separação do cliente e da custódia, **sem declarar uma autoridade externa real**.

## Problema e propriedade desejada

G7 demonstrou que outro UID/SID local protege contra leitura e falsificação da chave pelo aplicativo de menor privilégio, mas **administrador/root** da máquina ainda pode restaurar o SQLite do custodiante e emitir outra reserva assinada para o mesmo evento. Assinatura verdadeira não impede repetição após rollback.

Requisito a homologar no futuro: autoridade independente deve manter estado monotônico e origem autenticada **fora da capacidade de escrita/restauração do administrador do host AION**; nenhuma transação ou ACK incerto permite reenvio automático de efeito. É **pré-condição**, não melhoria cosmética.

## G8 implementado e limites

O G8 usa **processos diferentes com socket TCP real em 127.0.0.1** e SQLite em diretório diferente do cliente; Ed25519 verifica evento original assinado por emissor sintético e reserva assinada por custodiante sintético. Runners Ubuntu e Windows exercem o mesmo teste. Não existe endpoint na internet, cobrança, conta/serviço ou efeito real.

- O cadastro original sintético vem de **emissor de evento** com pin fixado na inicialização do custodiante. O campo *claimed_event_id* enviado pelo cliente **não** determina a unicidade: usa-se (tenant, semantic_digest) autenticado por assinatura do evento fonte. Cliente não consegue simplesmente trocar o request_id e o ID autoalegado para obter segunda reserva, desde que evento fonte e estado do custodiante permaneçam íntegros.
- Uma única reserva SQLite é escrita com BEGIN IMMEDIATE, índice UNIQUE de identidade semântica e synchronous=FULL. Custodiante assina schema/issuer/tenant/event_ref/semantic_digest/seq/epoch/request_id/status/issued_at/expires com separação de domínio. Resposta **RESERVED_ONLY_NO_EFFECT**, jamais comprovante de execução.
- Se resposta TCP for perdida *depois do commit*, o cliente permanece **UNCERTAIN_ZERO_AUTO_RESEND**; reconsulta somente leitura pode informar **reserva presente, não efeito confirmado**. Se o custodiante estiver indisponível após reinício H0 ou fora da rede, **nenhum novo efeito** é autorizado; não há fallback local.
- Chave/pin errado, assinatura do emissor adulterada, expiração, epoch incompatível, recibo modificando estado para EFFECT_CONFIRMED precisam ser negados. Requisições concorrentes para mesma intenção só podem registrar uma reserva.
- **CONTRAEXEMPLO RED deliberado:** quem controla o host restaura o SQLite do processo custodiante a snapshot pré-reserva; a mesma Ed25519 assina nova reserva válida. G8, como G7, **não demonstra uma terceira parte independente**: localhost/processo não define fronteira de confiança root/admin. Raiz/estado fonte também são sintéticos.

## Comparação de caminhos da missão A190 — decisão provisória

| Via | A — SO/IPC local | B — host + custodiante remoto com raiz independente | C — serviço transacional gerenciado externo |
| --- | --- | --- | --- |
| Ganha | Regras ACL contra app sem privilégio; trabalho offline limitado | Resistência potencial a rollback do host AION, se credenciais/controle administrativo também forem separados | Retenção, ordenação/idempotência e auditoria potencialmente delegáveis por contrato explícito |
| Não garante automaticamente | Resistência a admin/root; autenticidade de evento/efeito terceiro | Independência se mesmo dono root controla backup, assinatura ou pin; qualidade/SLA; recibo verdadeiro | Idempotência sem chave de negócio correta; semântica de ACK desconhecida; propriedade da chave e contrato |
| H0 internet indisponível | Pode continuar leitura local; novo efeito permanece NO-GO por risco root | Nenhuma nova reserva/efeito; consulta local rotulada não verificada | Nenhuma nova reserva/efeito; consulta local rotulada não verificada |
| Infra/manutenção | Recursos do host existente, manutenção ACL/OS/IPC/SQLite; licença da biblioteca de laboratório sem compra específica | Host ou serviço separado, chaves/revogação, backups independentes, monitoramento, disponibilidade e suporte | Conta, API, quotas, retenção, lock-in, rede/egress, auditoria, backup, SLA e teste de reconciliação |
| FinOps | Sem mensalidade externa adicional específica neste ensaio; não corrigiu P0 | **Preço real não cotado**. Não contratar antes de dimensionar e provar caber no limite | **Preço real não cotado**. Estimar transações, armazenamento, requisições de conciliação e SLA antes de escolher |
| Situação | **NO-GO como raiz independente** | **CANDIDATO A VALIDAR EXTERNAMENTE** | **CANDIDATO A VALIDAR EXTERNAMENTE** |

**Preferência técnica provisória:** especificar requisitos de B/C em abstrato, medindo custo e provas de auditoria; **não há escolha de fornecedor nem autorização para contratar**. Teto operacional R$200/mês existente (até R$250 somente com aprovação pontual), já comprometido por despesas do ecossistema. O custo incremental admissível depende da margem disponível verificada, não de média hipotética.

## Obrigações contratuais ainda faltantes

1. HUMAN_OWNER com prova externa (Windows Hello/FIDO2 não equivale por si só a autorização de efeito), escopo, revogação, quarentena após perda/re-enrollment.
2. Emissor original de evento verdadeiramente independente, key-pinning verificável por terceiro, event_ref e semantic_digest determinísticos ligados a tenant/ação/versão; estabilidade após retries e casos cross-tenant.
3. Custodiante com identidade e chave pública distribuída por canal independente do aplicativo, revogação/rotação/versionamento, controle de rollback fora do host local, política de expiração/horário validado, monotonicidade entre restaurações e falhas.
4. Recibo autêntico **do fornecedor de efeito**, idempotência por identificador de negócio que o fornecedor reconhece, etapa de envio único, sem replay e sem auto-resend, reconciliação assinada após UNCERTAIN.
5. Corte abrupto H0, energia, clock drift, isolamento de rede, key loss, restore conjunto, reaparecimento de autoridade anterior, concorrência e reorder Windows/Ubuntu/produção.
6. Auditoria CI e Quality/Security canônicas completas, 5 external-RED por SO, 43 advisories herdados e os seis P0 com evidência externa independente.

## Gates e proibições

- Processos diferentes **no mesmo runner** não são host independente. A sugestão arquitetural B/C permanece **pendente de prova**.
- Runners GitHub Actions são ambientes efêmeros; não contêm dados reais nem chaves operacionais. Este PR não altera paths do runtime, gateway financeiro, UI, Worker ou contratos de cliente.
- Nenhum fallback para lab_verified, assinatura autocertificada, timeout tratado como não-enviado ou rollback local assumido como inofensivo.
- **0/6 P0 homologados. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**
- Sem main/merge/deploy/Worker/efeito, serviço pago, autenticação real, credenciais, cliente, faturamento, contratação ou aumento de teto sem Mikael.
