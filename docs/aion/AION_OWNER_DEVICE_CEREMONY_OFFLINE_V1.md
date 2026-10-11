# HUMAN_OWNER e dispositivo — contrato executável, sem matrícula

Estado: HARD NO-GO. Implementação: `ceremony.prepare_intent`, `ceremony.review_ceremony`, `contracts.production_authority`. Não há WebAuthn real, leitor de hardware, biometria, chave privada ou callback de aprovação instalado.

## Vínculo exato

O schema fechado vincula owner, tenant, workspace, dispositivo, credential ID, repositório, branch, caminho lógico, resource ID, digest do artefato, operação, permissões e geração de política. O intent acrescenta request ID, nonce não nulo e janela de validade de até 180 segundos. Uma cópia da coleção de permissões evita alteração silenciosa pelo chamador. Cada alteração nesses campos invalida a correlação com a expectativa recebida.

A assertion de teste exige origem/RP `.invalid`, presença e verificação explícitas, decisão `APPROVE_THIS_SIMULATION_ONLY`, nonce/request/digest iguais e credencial não revogada. Histórico de nonce/revogação ausente é UNKNOWN, não lista vazia implicitamente confiável. O resultado positivo é `REFERENCE_CEREMONY_CONSISTENT_UNTRUSTED`; não é assinatura criptográfica, identidade autenticada ou consentimento válido de produção. ADMIN ou a string HUMAN_OWNER não satisfazem o contrato.

## Integração futura proposta — não implementada

1. Definir quem comprova a identidade real e quem pode matricular o papel HUMAN_OWNER, fora do repositório e da sessão ADMIN. Preservar evidência privada mínima, sem documento pessoal em GitHub.
2. RP autenticado e aprovado gera desafio CSPRNG e persiste o vínculo exato antes da cerimônia. Chave pública matriculada por outra etapa autorizada; nunca aceitar o pin enviado pelo próprio requerente como raiz.
3. Windows Hello/FIDO2 realiza a presença/verificação na interface nativa, sem exportar chave privada. O RP verifica challenge, origin, RP ID hash, assinatura, flags UP/UV, credencial e revogação. Esta preparação não implementa esse verificador.
4. Avaliar attestation e modalidade da credencial conforme equipamento/política. Credenciais sincronizáveis ou autenticadores externos não demonstram automaticamente que aquele PC Windows é o único dispositivo autorizado. Contador da credencial não substitui ledger monotônico/witness.
5. Decisão do proprietário, separada da autenticação, assina/acknowledge o vínculo da operação e registra validade/revogação. Inventory, instalação, gasto, merge, deploy e ativação são decisões distintas.
6. Admissão durável de uso único e revogação independente devem ser reverificadas na fronteira de execução. A leitura posterior de um digest não elimina risco físico de troca do artefato/caminho/ACL. Revalidar artefato e identidade do arquivo antes de uma execução futura aprovada.

Não há dependência circular de prova: a matrícula inicial de identidade/chaves precisa vir de cerimônia fora de banda, não de um checkpoint que ainda depende dessas mesmas chaves para ser confiável. `plan.collection_layers` documenta a ordem de coleta, não autoriza criar recursos pagos.

## Fontes primárias consultadas

[Microsoft: como Windows Hello for Business funciona](https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/how-it-works) descreve registro da chave pública e proteção local da privada; isso não comprova a configuração do PC do proprietário. [W3C WebAuthn Level 3](https://www.w3.org/TR/webauthn-3/) distingue presença/verificação, vínculo de origem/RP e verificação de attestation. [Microsoft: saúde/attestation de dispositivos](https://learn.microsoft.com/en-us/windows/security/operating-system-security/system-security/protect-high-value-assets-by-controlling-the-health-of-windows-10-based-devices) descreve evidência de boot enviada a um serviço externo; não usamos nem matriculamos tal serviço nesta missão.

BitLocker, TPM, AppContainer, Windows Hello, FIDO2 e assinatura do instalador permanecem UNKNOWN quanto ao dispositivo real. Nenhum comando físico foi executado para coletá-los.
