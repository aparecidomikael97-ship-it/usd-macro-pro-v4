# AION Collector Root Ceremony — PREPARE-ONLY V1

**Draft / synthetic CI-only / no physical host modification / NO ENROLLMENT.**

Esta etapa prepara a decisão para a raiz independente do coletor físico
e preserva o fail-closed. Não gera chaves reais, não escreve Trusted Roots,
ACL, TPM, registro, WFP, Firewall, AppContainer ou banco de produção.

## Protocolo de preparação

1. Verificar o registro owner/root já existente usando os mecanismos #1092:
   raiz Ed25519 ANTERIORMENTE fixada pelo host, subject/issuer,
   dispositivo ativo, epoch mínimo e chave HUMAN_OWNER ativa.
2. Receber do host uma política protegida, INDEPENDENTE dos dados recebidos:
   fingerprint da testemunha externa, host/device binding, epoch mínimo do
   coletor, fingerprint da raiz anterior em rotações, SHA-256 do binário e
   manifesto observados independentemente.
3. Validar uma proposta canônica com schema e purpose exclusivos
   PREPARE_ONLY_NO_ACTIVATION, nonce de 256 bits, TTL no máximo 120 segundos,
   contador igual exatamente a floor protegido + 1, modo inicial ou rotação.
   Bootstrap quando epoch anterior = 0; rotação somente com raiz anterior
   pinada e sem reutilizar a antiga.
4. Exigir que HUMAN_OWNER assine a proposta com a chave ativa derivada
   do registro previamente confiável.
5. Exigir a assinatura da testemunha independente previamente fixada no host,
   separada da chave do owner, da raiz proposta e da raiz do registro.
6. Exigir prova de posse pela nova raiz proposta, assinando a mesma proposta
   com domínio criptográfico distinto.
7. Exigir um snapshot #1095 completo, com host/device, epoch, collector ID,
   binário/manifesto idênticos aos independentemente observados e SHA-256
   integral vinculado à proposta. A nova raiz deve assinar o snapshot.
8. Consumir o nonce SOMENTE DEPOIS dos quatro checks de assinatura, de
   correspondência de política e de snapshot, com SQLite durável no CI.
   Mensagens alteradas com o mesmo nonce são recusadas.

## Limites — indispensável para a segurança

Mesmo com todas as verificações válidas, o máximo resultado é:

OWNER_COSIGNED_COLLECTOR_ROOT_PREPARED_UNTRUSTED

A proposta NÃO autoriza publicar/instalar a nova raiz no sistema, não inscreve
chave, não dá confiança ao coletor, não ativa instalador, não prova hardware
TPM/Windows Hello, nem executa teste de rede ou sandbox. Root,
HUMAN_OWNER, witness e collector usam apenas chaves efêmeras no CI.

Não existe o código de COMMIT, ACTIVATE ou INSTALL. A execução futura de
enrollment exige aprovação explícita separada, mecanismo host-side com
armazenamento protegido e proteção real contra rollback, testemunha
independente verificável, retenção/limpeza de segredo e auditoria física.

A vulnerabilidade principal que evitamos: não aceitar o 'expected host policy',
o pin da testemunha ou a raiz owner enviados pelo mesmo coletor que pede
inscrição; sem confiança preexistente, as quatro assinaturas podem apenas
demonstrar consistência interna, nunca identidade do proprietário.

## Portas que permanecem BLOQUEADAS

- collector_launch_authorized = false
- trusted_host_policy_mutated = false
- root_enrolled_in_production = false
- collector_enrolled_in_production = false
- physical_root_custody_verified = false
- physical_attestation_verified = false
- network_deny_verified = false
- installer_authorized = false
- build_authorized = false
- deploy_authorized = false
- safe_to_resume = false

Pré-requisitos futuros: root-of-trust real, recebimento segregado da
autorização do proprietário, witness independente já pinada,
antirollback externo ao banco de testes, medição de binário independente,
12 provas físicas #1049, 16 superfícies de rede #1087.

Nenhuma escrita em main, merge, deploy, Worker, Render ou despesa neste bloco.
