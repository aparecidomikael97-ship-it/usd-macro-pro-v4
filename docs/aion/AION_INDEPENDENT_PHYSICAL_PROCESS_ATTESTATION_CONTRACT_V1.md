# AION — Independent Physical Process Attestation Contract V1

## Estado

**DRAFT / CI-only / contrato de prova. Nenhum coletor físico é executado.**

Este bloco prepara a camada de prova independente que vem depois da #1092.
Ele não confia em booleanos declarados pelo processo testado e não promove
documentos ou assinaturas sintéticas a “sandbox físico verificado”.

## Desafio emitido pelo host confiável

O desafio canônico vincula:

- digest da pré-autorização rooted HUMAN_OWNER da #1092;
- digest do sandbox preflight;
- digest do plano físico #1049;
- host binding digest;
- collector manifest digest;
- collector binary digest;
- fingerprint da chave pública do coletor, pinada pelo host;
- digest do caminho esperado da imagem;
- SHA-256 esperado da imagem;
- nonce de 256 bits;
- janela curta de validade (máximo 120 s).

A função não gera o nonce. Em produção ele terá que vir de uma fonte segura do
host, fora do coletor.

## Envelope assinado pelo coletor independente

O envelope precisa conter, sem campos extras:

- digest e nonce do desafio;
- fingerprint da chave do coletor;
- digest do caminho realmente observado e SHA-256 da imagem;
- file-identity digest;
- process-handle provenance digest;
- token evidence digest;
- Job Object evidence digest;
- exatamente os **12 requisitos canônicos de #1049**, na ordem original, cada
  um com digest de evidência positiva **e** digest de teste negativo distinto;
- referência opaca e SHA-256 do bundle bruto;
- `collected_at` e `valid_until`.

A validade do envelope é limitada a **60 s**, adotando a janela mais restritiva
necessária para a futura prova de rede.

## Os 12 requisitos importados diretamente de #1049

1. WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED
2. WINDOWS_JOB_OBJECT_LIMITS_PROOF_REQUIRED
3. CACHE_READ_ONLY_MOUNT_PROOF_REQUIRED
4. SOURCE_READ_ONLY_MOUNT_PROOF_REQUIRED
5. RUNTIME_READ_ONLY_MOUNT_PROOF_REQUIRED
6. OUTPUT_TEMP_ONLY_WRITE_PROOF_REQUIRED
7. SYMLINK_REPARSE_HARDLINK_ESCAPE_PROOF_REQUIRED
8. ENVIRONMENT_SCRUB_PHYSICAL_PROOF_REQUIRED
9. PINNED_PYTHON_BINARY_PROOF_REQUIRED
10. NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED
11. WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED
12. RESOURCE_LIMITS_PHYSICAL_PROOF_REQUIRED

O código importa `PROBE_REQUIREMENTS` da própria implementação de #1049;
drift de contagem, nome ou ordem falha.

## Independência e anti-replay

A assinatura do envelope usa uma chave de **coletor**, distinta da chave do
HUMAN_OWNER. O host precisa pinar a chave pública/fingerprint por canal
independente. O desafio só é consumido depois de:

1. validar o desafio;
2. validar todos os vínculos;
3. validar os 12 pares positivo/negativo;
4. validar a janela temporal;
5. validar a assinatura Ed25519 do coletor.

Depois disso, um replay key é gravado atomicamente em SQLite com WAL,
`synchronous=FULL` e `BEGIN IMMEDIATE`. Reutilização do mesmo desafio falha,
inclusive depois de reabrir o banco.

## Máximo resultado possível neste bloco

`SIGNED_PHYSICAL_PROCESS_EVIDENCE_CANDIDATE_UNTRUSTED`

Mesmo nesse estado, continuam **FALSE**:

- collector_key_enrolled_in_production
- collector_binary_independently_trusted
- raw_evidence_independently_reviewed
- physical_probe_executed
- physical_attestation_verified
- windows_sandbox_verified
- network_deny_verified
- safe_to_resume
- installer_authorized
- build_authorized
- deploy_authorized

Isso é proposital: um atacante também consegue criar sua própria chave e
“evidência” sintética. A criptografia só se torna confiança quando a chave,
binário e host forem realmente inscritos por processo separado e auditado.

## Próximo passo físico — ainda NÃO executado

Depois deste contrato ser validado em CI, o próximo estágio será um coletor
Windows mínimo, revisado separadamente, que:

- recebe um desafio do host;
- trabalha com handle/proveniência controlados;
- mede os requisitos autorizados;
- produz raw evidence determinística;
- assina o envelope com chave de coletor realmente inscrita;
- não decide sozinho se passou;
- encerra e limpa tudo;
- é verificado por processo independente.

Nenhuma chamada anterior bloqueada por regras de segurança será contornada.

Sem merge, deploy, instalação, mudança de firewall/WFP/AppContainer, execução
no PC do proprietário, Render, Worker ou gasto.
