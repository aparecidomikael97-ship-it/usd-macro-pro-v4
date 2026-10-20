# AtlasQuant / AION — Pacote P0 ampliado de admissão de evidências (LAB)

**20/10/2026 — proposta de auditoria estrutural sem autoridade, sem compras e sem mudança de runtime.**
Base: Draft #1362 (NÃO main). Este pacote contém 55 casos no filtro + 18 na matriz de seis P0 = **73 testes novos**.

## Problema de segurança específico
Uma assinatura matematicamente válida, um identificador AWS KMS, um recibo do fornecedor, um HEAD externo transcrito e um `verified=true` podem ser valores produzidos pelo MESMO adversário. Avaliar coerência entre eles não prova autenticidade de qualquer um. Separar **formato**, **vinculação interna**, **origem autenticada** e **autorização de efeito**.

## Frentes cobertas pelo novo revisor local
1. **Issuer/key:** ID, escopo, hash da chave, Ed25519 RAW, estado ACTIVE/REVOKED/UNKNOWN. Rejeitar algoritmo trocado, status negativo ou vínculo errado. Não verifica assinatura real.
2. **Último estado:** epoch, sequência, head e versão do objeto lida, com alegação de tempo até 120 segundos. A janela temporal é apenas uma validação de formato; quem informou a hora/versão pode mentir. Não há provas de consistência, antirollback ou ausência de fork.
3. **Challenge/nonce:** escopo + request ID + nonce + emissor + TTL de até 180 segundos. Testa replay detectável numa lista local **fictícia**, mas não tem cache durável e independente do executor. Um valor não presente não prova uso único.
4. **Revogação:** key ID, credential epoch, status e tempo; divergência e estado REVOKED/UNKNOWN bloqueiam. O revisor não faz consulta externa nem verifica assinatura de uma autoridade real.
5. **Recibo/Outbox/Saga:** vínculo request/intent; rótulos COMMITTED_EFFECT, NO_EFFECT_FENCED e UNCERTAIN. UNCERTAIN não vira NO_EFFECT_FENCED; rótulos alegados não constituem prova nem autorizam reenvio. Os 32 ERROR canônicos permanecem OPEN_NOT_WAIVED.
6. **Administração:** seis rótulos de controladores/root; colisões no mesmo pacote são diagnosticadas. Rótulos diferentes não demonstram segregação real de IAM, owners, recuperação MFA, chaves de deploy ou faturamento.

## Proibições no módulo LAB
- Toda saída tem `status=BLOCKED`, `allowed=False`, 17 flags de execução/efeito falsas e zero autorização da primeira operação.
- Nunca importar SDK AWS, emitir chave, ler Secrets, usar relógio da máquina, acessar HTTP, rodar Worker nem atualizar SQLite/arquivos do produto.
- Dados de entrada usam tipos primitivos e conjuntos exatos de campos; objetos hostis não são executados por comparação de igualdade.
- Na adulteração coordenada de TODOS os valores, a sintaxe pode permanecer coerente. Isso é um contraexemplo deliberado: **não** existe prova de confiança fora do host.
- Revisor LAB não deve ser conectado aos validadores A53/A76, Worker, Outbox ou produção.

## Como sair da engenharia de simulação e obter uma evidência homologável
A. **Canal externo de matrícula:** autoridade independente comprova posse do controle de chave e entrega sua chave pública a um verificador fora do computador AION, com recibo assinado e cadeia de revogação.
B. **Último head real:** serviço independente fornece checkpoint atual, inclusão e consistência verificada contra checkpoint anterior protegido do executor, com mecanismos de detecção de fork e restauração. Object Lock em uma versão não basta.
C. **Anti-replay durável real:** nonce gerado fora do host, consumido atomicamente em armazenamento externo à zona PITR; teste pós-reinício e replay simultâneo.
D. **Provedor com efeito autenticado:** demonstrar recibo causal real e comportamento da tentativa incerta; nenhuma primeira operação é reenviada por timeout ou ausência de mensagem.
E. **HUMAN_OWNER e H0:** validação física de consentimento, revogação e disponibilidade pós-reinício, mais review de contas/IAM por pessoa independente.
F. **Qualidade e testes originais:** repetir Security/Quality integrais. Rastrear os dois casos originais de SQLite de leitura/escrita; a matriz atual não possui IDs exatos para ambos. Não dar baixa com testes STAGING.
G. **FinOps:** custo total de logs, KMS, armazenamento, API, retenção, auditoria e recuperação precisa ser orçado separadamente; teto R$200/mês, eventual R$250 com aprovação expressa. Nenhuma contratação desta branch.

## Matriz objetiva
O arquivo `docs/aion/AION_P0_EXTERNAL_EVIDENCE_ADMISSION_CROSSWALK_LAB_20261020.json` enumera os seis P0, a natureza externa/física ou forense-canônica, três artefatos esperados por bloqueio e zero estado de homologação. Dezenove campos de execução/validação antigos não são alterados; a matriz referencia a matriz canônica original sem editá-la.

## Evidência e limites
Os 73 testes verificam somente as negações, comparações e rastreabilidade explicitadas. Não executam uma auditoria externa independente. A CI da branch Ubuntu/Windows deverá ser observada até a conclusão antes de alegar PASS. A Quality canônica anterior permanece 6.562 testes / 52 FAIL + 34 ERROR e Security A53 RED. Nenhum de seus 86 diagnósticos é dispensado por uma aprovação LAB.

**Veredito: HARD NO-GO; 0/6 P0; Worker OFF; ZERO_AUTO_RESEND.**
Refs: Issue #1357, Issue #1323, Draft #1362, AWS KMS Sign, RFC 9162.
