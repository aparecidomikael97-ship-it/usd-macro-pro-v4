# AION — Rooted Collector Enrollment + Raw Evidence Byte Verification V1

## Estado: somente CI, Draft, falha fechada

Este bloco é posterior ao coletor de leitura somente de #1094 e ao contrato
assinado #1093. É um verificador puro que NÃO cadastra nenhuma chave real nem
executa processos. O registro de inscrição do coletor é assinado por uma raiz
Ed25519 independente, cujo fingerprint e chave pública DEVEM vir de política
do host fora dos dados do coletor. Todos os testes usam chaves efêmeras.

## Cadeia de confiança simulada
1. Host fornece a raiz pinada, registry_id, issuer, host binding, device
   binding, collector_id e epoch mínimo independentemente.
2. Snapshot canônico contém uma única chave pública de coletor, binary digest
   e manifest digest, histórico de epoch e indicador de revogação.
3. A assinatura da raiz autentica a associação host/dispositivo/coletor.
   Snapshot anterior ao epoch mínimo ou coletor revogado bloqueia.
4. O desafio #1093 precisa corresponder aos digests de binary/manifest
   inscritos, ao host e ao fingerprint da chave ativa do coletor.
5. A assinatura do coletor verifica a atestação canônica #1093.
6. O raw bundle JSON deve ser exato, canônico, limitado em bytes, sem campos
   repetidos ou extras. Deve vincular exatamente os 12 requisitos da #1049,
   na mesma ordem, com bytes positivos e negativos distintos por requisito.
7. O SHA-256 do raw bundle e o SHA-256 de cada amostra positiva/negativa devem
   coincidir com a atestação assinada. A verdade física dessas amostras NÃO é
   inferida pelos digests.
8. Só após todas as verificações criptográficas, o nonce do desafio é
   consumido via SQLite BEGIN IMMEDIATE e synchronous=FULL. A chave de
   replay deriva do nonce somente (separação de domínio), de forma que um
   mesmo nonce é recusado até se o atacante alterar o restante do desafio.

## Limite fundamental
Máximo estado: ROOTED_COLLECTOR_RAW_EVIDENCE_CANDIDATE_UNTRUSTED.

Mesmo em PASS:
- root_enrolled_in_production: FALSE
- collector_enrolled_in_production: FALSE
- raw_evidence_independently_observed: FALSE
- physical_attestation_verified: FALSE
- network_deny_verified: FALSE
- safe_to_resume: FALSE
- installer_authorized: FALSE
- build_authorized: FALSE
- deploy_authorized: FALSE

Assinatura e digests verificam proveniência RELATIVA À RAIZ CONFIÁVEL, não
demonstram que uma leitura, token, ACL, negação de rede ou processo realmente
aconteceu. Todos os bytes são sintéticos nos testes; um próprio coletor
comprometido pode mentir em suas amostras. A futura prova exige
collector binário medido por fonte independente, inscrição de chave com
custódia segura, armazenamento host-side protegido contra rollback e
medidas reais + testemunha independente para os 12 requisitos e 16 superfícies
de rede.

## Riscos de integração
- NÃO derivar a raiz, host binding ou epoch mínimo dos dados recebidos do
  browser, CLI ou coletor.
- Não expor a verificação de assinatura isolada da #1093 como endpoint que
  ignore esse gate.
- Não interpretar o banco SQLite do CI como armazenamento protegido do PC.
- Dados brutos reais podem conter informações privadas e precisam de
  retenção mínima, minimização/sanitização e proteção no host; nenhum dado
  físico real é enviado ao GitHub neste bloco.
- Sem alteração da main, deploy, Render/Worker, firewall, WFP, AppContainer,
  chaves reais, instalador ou gasto.
