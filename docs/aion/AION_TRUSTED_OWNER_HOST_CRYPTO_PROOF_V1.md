# AION Trusted Host — Ed25519 Owner Proof + Durable Replay V1

Data: 08/10/2026. **Draft; apenas protocolo local e provas sintéticas.**

## Problema resolvido nesta camada

A #1078 só pode funcionar com uma declaração `HUMAN_OWNER` confiável, sem deduzir privilégio de um login ADMIN. Esta camada adiciona **verificação real de assinatura Ed25519** de uma prova efêmera de proprietário, unida a valores esperados da sessão e dispositivo, com nonce consumido em SQLite local. Testes CI usam somente chaves efêmeras geradas em RAM, sem chaves reais do proprietário.

## Protocolo de prova

A parte confiável do host recebe uma prova com esquema/purpose fixos, sujeito, emissor/audiência esperados, digest da sessão, digest do dispositivo, fingerprint da chave pública, nonce de 256 bits e intervalo temporal de até 120 segundos. Os bytes assinados são canônicos e recebem separação de domínio `ATLASQUANT:AION:OWNER_HOST_PROOF:V1`.

O host **deve** fornecer fora da entrada do navegador: chave pública do proprietário previamente enrolada, fingerprint esperado fixado por autoridade confiável, digest da sessão *já autenticada*, digest do dispositivo *já conhecido*, audiência e emissor esperados, hora confiável e caminho de armazenamento protegido. A chave pública declarada na própria prova nunca é aceita como âncora de confiança.

`verify_host_owner_proof` recusa: assinatura incorreta, chave trocada, pin alterado, usuário não autenticado, subject divergente, sessão e dispositivo divergentes, prova vencida/futura, campo não reconhecido e nonce já consumido. O nonce é registrado atomicamente com `BEGIN IMMEDIATE`; um segundo consumo falha, inclusive após reabrir o mesmo banco de teste.

O retorno positivo **não é autorização de uma ação**: `CRYPTO_PROOF_VERIFIED_FOR_TRUSTED_HOST_REVIEW`, `authorizes_execution=false`, `authorizes_payment=false`, `trusted_host_attached=false`. A estrutura `owner_assertion` somente pode ser repassada à ponte #1078 **pelo processo de host confiável**, jamais produzida ou reescrita por UI/cliente.

## Limites e ameaças remanescentes

- Não cadastra chave privada, não assina pelo proprietário, não configura Windows Hello/FIDO2 ou reconhecimento facial.
- A seleção e proteção da chave pública são **externas** ao módulo. Fornecer um fingerprint escolhido pelo atacante faz a assinatura maliciosa parecer coerente: o pin precisa ser fixado por canal seguro de instalação/enrollment.
- Também são externas as provas de identidade, sessão, dispositivo, origem dos dados, estado da hora e proteção do diretório/banco por ACL/antirrollback/backup. Um invasor com controle do host ou banco pode invalidar a garantia de replay.
- SQLite é usado com persistência local **somente quando uma instância `SQLiteOwnerNonceRegistry` é criada explicitamente**. Nos testes, o banco reside em diretório temporário do runner, **nunca no computador do proprietário**. Em produção exigirá autorização e verificação de permissões do arquivo, isolação e recuperação.
- O protocolo de prova isolado não é uma certificação de identidade, uma sessão completa, uma prova de presença biométrica nem um substituto por um provedor de autenticação.
- Sem GitHub mutações, deploy, Worker, compras, chamadas de APIs pagas, gravações de memória/Core, microfone, reconhecimento de voz ou instalação. Teto FinOps **R$200/mês permanece provisório**.

## Testes de CI

Windows + Linux; `cryptography` fixado; 44 testes adversariais cobrindo SHA-256, assinatura, pin, nonce persistente, reabertura, 24 consumidores concorrentes, expiração e composição de prova positiva com a ponte #1078. CI não fornece segredos de produção nem faz rede durante testes (instala dependência pública no runner). Todo artefato de prova é teste.

## Próxima etapa dependente de PC/host

Auditar chave pública enrolada sob HUMAN_OWNER, recuperação/revogação/rotação e verificação independente da origem do pin e sessão. Em seguida, integrar o host autenticado à #1078 e validar funcionalmente a interface PC/celular. Nada disso é ativado por esta PR.
