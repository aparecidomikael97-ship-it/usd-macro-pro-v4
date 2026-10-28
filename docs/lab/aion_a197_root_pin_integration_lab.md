# AION A197 — ensaio offline de pin da raiz pública e integração (sem custo)

**27/10/2026 · LAB Draft · 0/6 P0 homologadas · HARD NO-GO.**

## Objetivo

Validar numa **única branch de compatibilidade** o conjunto de mudanças
previamente isoladas e ainda não mescladas:

- A195 [#1645]: revalidação da identidade da sessão no wrapper real Streamlit,
  com teste completo de navegador/login/logout/troca de duas contas sintéticas.
- A196 [#1646]: bloquear colisão do escopo de nonce assinado Ed25519 usando
  delimitador `|`, preservando nonces legados.
- Dependências seguras [#1635]: `streamlit==1.66.1`,
  `pypdf==6.21.2`, `pillow==13.0.0`, revisadas em sua PR Draft.
- A197: verificar o **manifesto completo** de raízes públicas contra digest
  SHA-256 esperado e exercitar assinatura Ed25519 com SQLite real em LAB.

Este bloco NÃO incorpora as PRs separadas A193/A194 de SQLite fechado/fallback
de login, nem mudanças comerciais/Twelve. Elas continuam sujeitas a revisão
e integração distinta. A branch parte da HEAD da A195 e não da produção.

## O que A197 prova e NÃO prova

`labs/a197_offline_owner_root_pin_lab.py` produz só
`LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION` ou `BLOCKED`.
A digest cobre chaves, versões, janelas, status e revogações. A digest esperada
deve vir de fora do campo controlado pelo próprio emissor, mas **este LAB não
possui nem comanda uma fonte independente**. A função recusa digest ausente,
manifesto malformado, troca de chaves, revogação e assinatura inválida.
A estrutura de saída marca permanentemente como falsas:

- `external_owner_provenance_verified`
- `independent_root_custody_verified`
- `independent_anti_rollback_verified`
- `human_owner_enrollment_verified`
- `execution_allowed`, `approval_implied`, `provider_called`

**RED indispensáveis mantidos e provados:**

1. Se um atacante puder fornecer outra chave **e** substituir a digest
   supostamente pinada, o verificador local aceita assinatura dele. Portanto,
   pin local de fonte autoatestado NÃO identifica o HUMAN_OWNER.
2. Um histórico SQLite local apagado/restaurado com registro de nonce antigo
   pode permitir reapresentar exatamente o mesmo statement assinado; uma
   cópia em DB novo reproduz o fenômeno sem simular uma custódia externa.
3. A atualização de dependências pode eliminar advisories na branch, mas
   não resolve custódia, CAS, preservação de identidade/eixo temporal nem
   prova causal de efeito do provider.

## Critérios antes de qualquer revisão humana

- Workflow dedicado `AION A197 Offline Root Pin LAB`: 17 testes Python
  sintéticos em Ubuntu e Windows com Ed25519 real e SQLite real.
- Workflow A196 dedicado para contratos de nonce: 13 testes por OS.
- Quality e browser real, AION Core Certification, Release Readiness,
  Unified Core, Core Security Gate inclusive pip-audit, sem mascarar falhas.
- Se CI falhar, manter Draft e registrar causa; não alterar G122 RED.

**Não conectar A197 à autenticação de clientes nem ao executor real.**
É um controle demonstrativo, não enroll de chaves HUMAN_OWNER.

## Governança do proprietário

Negócios congelado em 27/10/2026. AION/Trader/Investimentos prioritários.
Nenhum gasto/contratação adicional até 05/11; possibilidade de avaliar
após 06/11 não concede aprovação automática. Sem AWS, Worker, provider
SEND, ordens, faturamento, merge, deploy ou uso de chaves reais.
