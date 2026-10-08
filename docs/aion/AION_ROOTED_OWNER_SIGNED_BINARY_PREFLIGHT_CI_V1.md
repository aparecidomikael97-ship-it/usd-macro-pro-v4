# AION — Rooted Owner Signed Pinned Binary Preflight CI V1

## Estado

**DRAFT / CI-only / fail-closed. Não autoriza execução.**

Este bloco liga a proteção de executável validada na #1091 a uma identidade de
proprietário derivada de um registro Ed25519 assinado por uma raiz que precisa
ser pinada fora do payload. Ele também consome de forma atômica um identificador
de replay persistido em SQLite depois de todas as verificações criptográficas,
temporais, de caminho e SHA-256 terem passado.

## Cadeia verificada

1. O host fornece uma chave pública raiz e fingerprint esperadas por canal
   independente.
2. Um snapshot canônico de registro é validado pela assinatura dessa raiz.
3. O registro precisa corresponder exatamente a registry id, HUMAN_OWNER,
   emissor, epoch mínimo e dispositivo esperados pelo host.
4. O dispositivo precisa estar inscrito e não revogado.
5. Exatamente uma chave do proprietário precisa estar ativa; rotações antigas
   precisam estar revogadas e encadeadas.
6. A chave ativa resolvida do registro verifica o manifesto de executável da
   #1091.
7. O manifesto continua restrito a
   `QUARANTINE_NORMAL_CHILD_NEVER_RESUME`, com validade máxima de 120 s,
   caminho Windows absoluto normalizado, SHA-256 exato e nonce.
8. Caminho e SHA observados do processo suspenso precisam corresponder ao
   manifesto.
9. Somente então um replay key que inclui registro, chave, nonce e manifesto é
   inserido atomicamente em SQLite com `BEGIN IMMEDIATE` e
   `synchronous=FULL`. Uma segunda tentativa falha.

## O que um PASS significa

Um PASS significa apenas:

`ROOTED_OWNER_SIGNED_BINARY_PREFLIGHT_CANDIDATE`

Ele demonstra em fixtures sintéticas que a assinatura do manifesto está
criptograficamente ligada à chave ativa de um HUMAN_OWNER dentro de um registro
assinado por uma raiz pinada e que a autorização não foi reutilizada naquele
store.

Mesmo no PASS, permanecem **FALSE**:

- `production_owner_identity_verified`
- `trusted_host_attached`
- `physical_attestation_verified`
- `appcontainer_verified`
- `network_deny_verified`
- `safe_to_resume`
- `installer_authorized`
- `build_authorized`
- `deploy_authorized`

## O que ainda falta para confiança física

Este CI usa raiz, chave do proprietário e dispositivo sintéticos. O SQLite está
em armazenamento temporário do runner e não comprova ACL/anti-rollback físico.
Ainda faltam, em bloco separado e com consentimento específico:

- inscrição/custódia real da raiz e chave do HUMAN_OWNER;
- proteção do epoch mínimo e banco de replay por ACL/anti-rollback;
- coletor físico independente assinado e vinculado ao dispositivo autorizado;
- prova de identidade do objeto de arquivo contra escritores previamente
  abertos, hardlinks/reparse e troca de seção carregada;
- AppContainer real com SID/capabilities esperados;
- prova independente das 16 superfícies de negação de rede da #1087;
- fechamento das 12 categorias físicas do plano #1049;
- decisão separada e explícita antes de qualquer caminho positivo de execução.

## Segurança operacional

Este módulo não cria processo, não chama APIs de resume, não altera firewall,
WFP ou AppContainer, não abre socket, não baixa artefato, não instala pacote no
PC do proprietário e não toca em produção. O workflow instala
`cryptography==50.0.2` somente no GitHub-hosted runner para os testes.

A PR permanece Draft, empilhada na #1091. Sem merge, deploy, Render, Worker,
gasto ou alteração da main.
