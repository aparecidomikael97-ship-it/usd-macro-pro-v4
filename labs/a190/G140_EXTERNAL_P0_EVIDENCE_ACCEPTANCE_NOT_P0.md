# A190 / G140 — Aceitação externa: cinco exigências reais e controle contra falso GO

**Status: LAB, 0/6 P0, HARD NO-GO, UNCERTAIN/ZERO_AUTO_RESEND.** Empilhado na PR #1631 G139. Não implementa nem contrata serviço externo.

## Por que não continuar adicionando assinaturas sintéticas?

G134–G139 melhoraram os **contratos e as provas negativas locais**, mas demonstraram que um host que controla as raízes, arquivos ou SQLite pode substituir o cadastro original, forjar a permissão de staging ou restaurar a sequência histórica. O G138/G139 não fornece um custodiante externo. G140 inaugura um intake **estritamente não autorizador** que indica quais obrigações faltam para futura homologação. Um PDF, CSV, JSON, print, GitHub CI verde ou fingerprint fornecido pelo próprio host não provam independência por declaração.

## Cinco testes de aceitação externa CANÔNICOS

| Teste G122 real (não alterar) | Evidência que falta de verdade | Aceitação mínima |
| --- | --- | --- |
| `test_custody_plus_checkpoint_rollback_must_not_reauthorize` | Estado monotônico retido fora do domínio de rollback do AION | Restaurar host/custody local NUNCA reautoriza o mesmo primeiro efeito |
| `test_replacement_original_enrollment_must_be_detected` | Pré-registro original/identidade HUMAN_OWNER autenticados por terceiro independente | Host não pode criar/substituir identidade original com uma chave nova |
| `test_replacement_trust_root_and_fingerprint_must_be_detected` | Raiz pública/epoch pinados de modo independente, rotação autenticada e auditada | Trocar raiz/fingerprint local não legitima nova autoridade |
| `test_live_restore_same_inode_must_be_attested_before_read` | Prova de identidade e versão de snapshot autenticada antes de READ da conexão SQLite NATIVA aberta | Restaurar bytes mantendo inode deve bloquear leitura antes de confiar no conteúdo |
| `test_live_restore_same_inode_must_not_reopen_write_authority` | Barreira de escrita nativa efetiva, não apenas um trigger opcional | Mesmo inode restaurado não reabre autorização de WRITE/SEND |

Os cinco testes são cinco obrigações de aceitação externa, NÃO equivalem automaticamente às seis P0. O G140 confere que esses nomes continuam intactos; não mascara o G122 nem altera sua configuração. As demais obrigações de P0 incluem idempotência econômica real/provider e ligação atômica/obrigatória ao caminho de efeito, além da autenticidade de origem. O status permanece 0/6.

## Contrato de intake — nunca é uma prova de autoridade

`evaluate_p0_external_evidence_lab(dossier)` aceita apenas documento com:
- `schema`, commit exato e cinco entradas únicas relacionadas aos nomes reais de G122.
- Em cada linha: `case_id`, `claimed_result`, `source_kind`, `source_identifier`, `artifact_sha256`, `independence_claimed`, `reviewer_claimed`.

Toda entrada é **DECLARAÇÃO NÃO VERIFICADA**. Hash SHA-256 correto não comprova quem criou o artefato. Nome de revisor não é assinatura. `source_kind=independent_external_claimed` significa apenas *alegação*. Nenhuma saída tem campos `allows_worker`, `allows_provider_send`, `allows_retry` ou `externally_verified` verdadeiros. A saída com todas as cinco alegações completas é `EXTERNAL_CLAIMS_REQUIRE_INDEPENDENT_ADJUDICATION_HARD_NO_GO`, nunca GO. Dossiês com CI sintético ou banco do mesmo host geram `DENY_SELF_ATTESTED_EVIDENCE_HARD_NO_GO`. Dossiês incompletos, G122 aberto e dados inválidos continuam HARD_NO_GO.

## Próximo requisito que depende de capacidade/infraestrutura externa real

Antes de propor implementação para homologação, é necessário identificar um **custodiante independente** com:
1. **Controle de autoridade fora do host:** chave e cadastro de HUMAN_OWNER criados/retidos fora da influência do computador; comprovação externa do domínio de controle e rotação. Um subprocesso, trigger, repositório da mesma conta ou arquivo com ACL não é independência suficiente.
2. **Reserva original atômica por efeito econômico:** evento semântico autenticado com idempotência vinculada ao destino/pagamento real, sequência e ACK verificáveis depois de perda de resposta; recusa sempre que o resultado externo for desconhecido.
3. **Proteção contra rollback e ataque ao mesmo inode:** leitura/WRITE nativos falham fechado mesmo com restauração hostil; não são substituíveis por checagens Python voluntárias.
4. **Prova da outra ponta:** recibo real de provider ou reconciliação autêntica que distingue efeito inexistente de efeito possivelmente já realizado, sem reenvio às cegas.
5. **Teste de aceitação sob controle independente:** repetir cenários reais de G122 em Ubuntu/Windows com logs, fingerprints, proveniência verificável fora do host e adversários que podem controlar AION, mas NÃO o custodiante externo.

**Decisão operacional:** requisitos e testes primeiro. Qualquer serviço, conta, credencial, cobrança ou efeito externo precisa de autorização explícita do proprietário e respeito ao teto financeiro atual; NÃO foi configurado nem gasto nada nesta etapa. O laboratório atual não pode homologar nenhuma P0 por si só.

## Testes G140
19 casos adversariais: ausência de dados, cinco alegações "pass", fontes sintéticas, CI local, um caso contaminando conjunto, requisito omitido/duplicado/inventado, enum incorreto, G122 verdadeiro unmet, artefato hash inventado, campos extras, booleano malformado, injection no revisor, ordem diferente, tentativa de sobrepor estado Worker/SEND e introspecção dos **cinco testes reais** de G122. Todos exigem **0/6 P0 e NO-GO**. Uma bateria G140 verde demonstra somente que o intake não confunde alegação com prova externa.
