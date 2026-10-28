# A198 — Consolidação transversal das correções de segurança A193–A197 (LAB / DRAFT)

Data: 27/10/2026. **Sem merge, deploy, Worker, SEND, AWS, chave real ou despesa nova.**

## Motivação

A193 (#1643), A194 (#1644), A195 (#1645), A196 (#1646) e A197 (#1647)
foram validadas isoladamente, mas as mudanças em `aion_chat/store.py`,
`atlasquant_access_panel.py`, `usd_macro_pro_v4_cloud.py`, os wrappers
Streamlit, o verificador Ed25519 e as versões de dependências devem coexistir
em uma única base antes de qualquer revisão de integração.

Esta branch **parte diretamente do HEAD de #1647**
`a6de9c224fb8f4779a478bf21518104c6ba2a9e2`, acrescentando as
implementações originais não mescladas da A193 e A194, além de todos os seus
testes e workflows. Nenhuma alteração foi feita em `main`.

## Matriz de proveniência

| PR fonte | Arquivos reais na branch A198 | Bateria própria |
| --- | --- | --- |
| #1643 — A193 | `aion_chat/store.py` | 23 testes SQLite fechado, Ubuntu/Windows |
| #1644 — A194 | `atlasquant_access_panel.py`, `usd_macro_pro_v4_cloud.py`, teste legado atualizado | 25 testes reais de login/fallback via AST, Ubuntu/Windows |
| #1645 — A195 | `atlasquant_aion_chat_entrypoint_guard.py`, host staged e produção, QA navegador | 36 testes de sessão, SQLite e wrappers, Ubuntu/Windows |
| #1646 — A196 | `atlasquant_aion_authority_verifier.py` | 13 testes assinatura real Ed25519 + nonce SQLite, Ubuntu/Windows |
| #1635 / #1647 | `requirements.txt` Streamlit 1.66.1, Pillow 13.0.0, pypdf 6.21.2 | pip-audit + CI geral |
| #1647 — A197 | `labs/a197_offline_owner_root_pin_lab.py` | 17 testes Ed25519, root pin, rollback local, Ubuntu/Windows |

Esperado por SO: **114 testes focados** (23 + 25 + 36 + 13 + 17).
Aprovação individual anterior não comprova sucesso da A198; exigir
CI real e inspecionar logs dessa HEAD.

## Gates fundamentais / NÃO homologados

1. **HUMAN_OWNER:** root registrada com custodiante independente, autoridade
   de inscrição e revogação efetivamente fora da host AION; digest auto-pinado
   e assinatura sob chave fictícia não bastam.
2. **Intenção econômica original:** identidade semântica imutável,
   first-attempt CAS independente, uma única reserva persistente.
3. **Duplo rollback:** restauração conjunta de AION + SQLite local + arquivo
   witness + raiz não pode reabrir uma operação; prova da recusa de autoridade
   externa precisa vir de outro principal/host.
4. **Efeito do provider:** recibo causal de COMMITTED_EFFECT ou
   NO_EFFECT_FENCED verificável e associado ao evento original; falta de ACK
   é UNCERTAIN/ZERO_AUTO_RESEND, nunca permissão de retry.
5. **SQLite VFS/native:** atestação read/write contra restore live same-inode
   em Windows e Ubuntu, com ACL/principal real e teste do kernel/host.
6. **Provas H0/G122:** cinco assertions externas verdadeiramente RED por OS
   em linhagens anteriores; não são alteradas ou silenciadas por este pacote.

Todas as políticas operacionais seguem **HARD NO-GO, 0/6 P0 homologadas**.
Mesmo que todos os workflows de produto fiquem verdes, esse resultado diz
apenas que as mudanças do pacote não falharam nos cenários testados.

## Financeiro e produto

Negócios congelado pela autorização explícita de 27/10.
Foco AION + Trader + Investimentos.
Nenhum novo gasto/contratação até 05/11/2026; a partir de 06/11 apenas
reavaliar mediante consentimento específico. Limite de referência
R$250/mês TOTAL, verificar despesas reais antes de qualquer contratação.
Sem AWS provisionada, KMS, recursos WORM, contato com clientes, cobrança,
ordem real, provider SEND, Worker, merge ou deploy automático.
