# A190 G7 — signatário Ed25519 em principal do SO distinto, contraexemplos ROOT/ADMIN

**Data local:** 2026-10-23. Missão #1486. Somente LAB Draft sobre G6 #1493; nenhum efeito operacional, fornecedor, cliente ou chave verdadeira.

## Por que este bloco não repete G1/G2/G6

- G1/G2 comprovou ACL de banco e piso local sob dois UIDs/SIDs, além de restauração por administrador/root.
- G6 comprovou que o Outbox real recebe callbacks Python não autenticadas; basta o chamador retornar True para simular autorização/recibo.
- G7 conecta **papéis de sistema distintos** a um **assinador Ed25519 REAL**, uma chave privada cujo acesso é negado pelo SO ao usuário de menor privilégio, e um SQLite local do custodiante que verifica unicidade de event_id. A assinatura e a verificação são operações criptográficas reais. Todos os eventos/chaves são sintetizados no runner.
- G7 também reproduz limites: falsificação sob raiz escolhida pelo atacante, dois IDs distintos para o mesmo hash/intenção sintética e restauração do diário pelo administrador que permite emitir outro recibo válido para o MESMO event_id.

## Contrato e papéis do experimento

| Elemento | Dono/autorização | O que pode ser provado | Limite |
| --- | --- | --- | --- |
| Diretório privado / chave raw Ed25519 | Usuário OS custodiante; ACL somente custodiante + root/admin | Aplicativo de UID/SID distinto não consegue ler chave/DB | Root/admin pode ler/substituir tudo |
| Diretório público / pubkey hexadecimal / recibos JSON | Custodiante escreve, app lê | App verifica assinatura sobre payload canônico e domain separator | Public pin está no mesmo host/conta administrável; não é ancoragem independente |
| Tabela SQLite de original_event | Custodiante, UNIQUE por original_event e request | Dupla requisição do mesmo ID negada enquanto histórico íntegro | IDs autoalegados; restore admin elimina reserva |
| Recibo de reserva com seq/epoch/issuer/action/intention_hash | Assinado no CLI do custodiante | Matemática Ed25519 aceita original e recusa falsificação contra pubkey retida | Não é recibo real de fornecedor nem autenticidade do original |
| App de menor privilégio | Lê recibo, tenta ler chave, gera falsificação | OS_DENIED para chave/SQLite e falha criptográfica sob pin correto | Pode criar sua própria chave e raiz e obter assinatura autoconsistente |
| Administrador/root da mesma máquina | Pode repor snapshot antigo de SQLite privado | Demonstra reemissão após rollback (RED) | Faltam host independente, HW antirollback e provedor |

## Casos de aceitação/recusa executáveis

1. Verificar no log **UID real** de app/custodiante em Ubuntu e **SID real** de subprocessos distintos em Windows, ambos exercendo a mesma CLI sintética.
2. Custodiante gera chave e assina reserva e1/r1. App valida Ed25519 usando public key publicada e responde somente lab-verified, nunca permits_send.
3. App de identidade separada tenta ler bytes reais de chave privada e abrir SQLite real em modo rw. Ambos devem gerar **negação OS comprovada**; se um deles abrir, falhar a CI.
4. App fabrica outra chave e recibo para o mesmo payload. Verificação contra pin original precisa NEGAR; verificação contra a sua própria raiz forjada vai aceitar matematicamente (**RED**). Sem pin imutável externo, confiabilidade não é estabelecida.
5. Custodiante nega repetir e2 sob request diferente quando já reservado. Mas e1/e2 podem ter o mesmo hash/intenção original sintetizada, por IDs autoalegados: ambos recebem recibos válidos (**RED**).
6. Runner administrador/root restaura um snapshot do diário do custodiante guardado entre e1 e e2; o custodiante emite r4 para e2 novamente, com assinatura válida (**RED**). Isto não seria possível com um piso monotônico independente retido.

## Protocolo de produção ainda faltante

- Independência real de raiz/epoch e de custódia exige controle fora do host/administrador do AION, não apenas outro processo ou usuário local.
- ID de evento deve vir de principal autenticado, não do campo livre do chamador; idempotência de efeito deve ser garantida/reconciliada pelo fornecedor externo real.
- Recibo precisa comprovar o efeito e primeira reserva, com nonce/desafio, validade, revogação, scope tenant/owner, sequenciamento persistido, autenticação de provedor e auditabilidade após H0.
- Chave publicada e pin não podem ser substituíveis pelo mesmo ator capaz de restaurar SQLite. A rotação e o re-enrollment precisam ser formalmente autorizados.
- H0 offline sem custódia/raiz disponível = DENY novo efeito; leitura local rotulada desatualizada/não verificada. ACK ambíguo mantém UNCERTAIN / ZERO_AUTO_RESEND.
- Serviço externo não foi escolhido, adquirido, cotado ou provisionado. Teto de R$200/mês, até R$250 só sob aprovação pontual; proposta futura requer preços/contratos verificados e escolha do proprietário.

## Evidência e NO-GO

Workflow A190 G7 com dois **usuários SO reais** por plataforma, Python 3.12 e cryptography 50.0.2, no GitHub Actions, sem chave persistente. **CI ainda não verificada ao criar este arquivo**, não contar os testes como conclusos sem run ID/SHA/logs por OS.

Quality/Security canônicas e requisitos external-RED (cinco por SO), 43 advisories herdados, VFS/WAL/SHM/H0/power loss e P0 permanecem não homologados; a prova local Ed25519 não fecha esses gates.

**0/6 P0 — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND**. Sem main/merge/deploy/Worker, efeito real, gasto, credencial ou contratação.
