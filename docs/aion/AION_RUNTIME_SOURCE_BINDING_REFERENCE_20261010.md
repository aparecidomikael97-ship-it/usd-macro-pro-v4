# AION — origem do checkpoint: referência offline (10/10/2026)

**Escopo:** issue #1178. Base Draft #1177, SHA eddede05be0b36cc99617166abf875ab4323ef2e.

**ESTADO: REFERENCE ONLY / NOT WIRED / PARTIALLY_CLOSED / HARD NO-GO.**

## Lacuna P0

O loader atual diferencia status do transporte, decodificação e integridade do conteúdo. Integridade de componentes e SHA GitHub não comprovam a propriedade externa do arquivo (owner/tenant/workspace), a matrícula de chaves, frescor independente ou monotonicidade antirollback. O CAS, fencing e os gates anteriores do Worker permanecem essenciais. Este registro não prova incidente.

## Conteúdo deste Draft

- atlasquant_aion_runtime_source_boundary_ref_v1.py: referência pura em memória com verify_source_preflight() e guarded_checkpoint_reference_read(). Nenhuma chamada HTTP no módulo.
- Pré-leitura: exige owner/tenant/workspace exatos, repo/branch/path canônicos, duas assinaturas Ed25519 distintas de *source* e *witness*, chaves fixadas em snapshot EXTERNO hipotético, freshness de 300 segundos e piso monotônico inteiro.
- Pós-leitura: exige status CONFIRMED, blob SHA exato da prova, checkpoint presente e integrity.state=CONFIRMED; qualquer outro resultado retorna estado bloqueado, sem entregar dados.
- Recusa falta de prova, troca de chave, confusão de empresa, rollback, replay, payload com campos extras, SHA trocado, expiração, inconsistência de sequência, estado de gravação incerto e exceção.
- Testes com chaves SINTÉTICAS e mock de reader. Workflow on pull_request, read-only, Python 3.12, Windows e Linux.

## Limites de confiança IMPORTANTES

1. IndependentlyPinnedSource é apenas um tipo de valor recebido. O programa Python não prova que ele veio de instituição independente. Um caller malicioso poderia gerar suas próprias chaves e declarar um snapshot falso. Mesmo uma verificação positiva é **matemática sob pins recebidos**, não matrícula confiável ou autoridade real.
2. floor_sequence fornecido pelo processo não prova antirrollback sozinho. Precisa vir de testemunha monotônica realmente independente da cópia GitHub/backup/admin host, consultada com canal autenticado, proteção contra replay e relógio confiável.
3. Não há matrícula REAL de HUMAN_OWNER, P-256 TPM/attestation EK-AK, chaves reais, witness durável, recovery, namespace multiempresa real ou aprovação de operação. A prova usa somente dados sintéticos e offline.
4. **Nenhum entrypoint de produção chama o wrapper nesta PR.** Ligar um parâmetro trusted controlável pelo caller diretamente no Worker criaria uma falsa garantia; a integração real exige serviço externo com confiança já inscrita, custody e canal verificados. Até lá, Worker segue OFF / HARD NO-GO.
5. Não liberar writer, CAS, reconciliação de UNKNOWN_OUTCOME, nenhum rerun ou operação sensível por causa da saída desta referência.

## Sequência de integração futura, ainda sem autorização

A. Escolher método independente de enrollment de chaves e binding owner/tenant/workspace -> repo/branch/path, rotatividade, revogação e recovery, com custo conhecido e consentimento individual.

B. Implementar adapter que obtenha a prova diretamente do serviço autenticado (nunca de request, session_state, arquivo GitHub ou campo no próprio checkpoint). Integrar a falha fechada antes do GET/lease/execução e sustentar revalidação após readback/CAS.

C. Ampliar os testes em Linux/Windows a tenant A/B, resposta stale do witness, rollback do GitHub, prova substituída, assinatura incorreta, expirado, erro de relógio, rede indisponível, CAS/UNKNOWN e zero I/O nos negados.

D. Reservar Windows físico, TPM, enrollment, migração, build, merge, deploy, instalação, flag e qualquer gasto a autorizações específicas. Não tocar Core V1 congelado.

**As flags source_trust_production_verified, worker_authorized e automatic_retry_allowed permanecem FALSE mesmo na verificação sintética positiva.**
