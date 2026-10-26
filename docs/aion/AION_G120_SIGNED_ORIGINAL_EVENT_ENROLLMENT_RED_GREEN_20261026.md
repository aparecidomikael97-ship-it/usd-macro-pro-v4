# AION G120 — assinatura sintética da identidade original do evento (RED → GREEN)

**Data:** 26/10/2026. **PR:** Draft #1610, empilhada sobre G119. **Escopo:** laboratório; nenhuma conta, credencial de proprietário, Worker, deploy, SEND real ou fundo. **Seis P0: 0/6 HOMOLOGADAS; HARD NO-GO.**

## Falha REAL no contrato anterior, reproduzida antes da correção

O custodiante G113/G114 permitia `enroll_synthetic_only()` para um identificador de evento escolhido pelo mesmo cliente. O guard G115 apenas comparava esse identificador local com as respostas assinadas do custodiante, sem verificar uma inscrição original assinada por outra autoridade.

Resultado: o mesmo cliente podia cadastrar OUTRO `event_id` para a **MESMA decisão semântica original**, construir novo guard e obter nova autorização para o adaptador **falso de memória**. A assinatura G114 confirmava que o segundo evento estava no banco de TESTE, mas NÃO comprovava que uma autoridade humana o havia autorizado como evento distinto.

[CI RED 40391558626](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40391558626), no código G115 intacto:
- Ubuntu: 23 testes executados, **1 FAIL**. O resultado foi `CONFIRMED`, esperado `UNCERTAIN`.
- Windows: 23 executados, **1 FAIL idêntico**.
- Marcador de falha: `G120_RED: caller-invented event identity authorized another simulated first-attempt dispatch`.
- O adaptador era in-memory fake, sem rede/provedor ou efeito real.

## Correção mínima e mais explícita no contrato LAB

`labs/a190/g120_synthetic_owner_enrollment_lab.py` verifica envelope Ed25519 com domínio G120 independente do domínio/assinador do custodiante G114. A prova fica vinculada a:
- identidade `event_id` que deve corresponder exatamente à identidade do primeiro evento aprovada;
- SHA256 canônico de toda a decisão original e `idempotency_key`;
- `owner_id`, `tenant_id`, `workspace_id`, ação, `policy_version`, `authorization_ref`;
- esquema e audiência fixos, identificador de aprovação, nonce de 64 caracteres hex;
- tempo de início/fim timezone-aware, janela positiva de validade de no máximo 10 minutos;
- chave pública do suposto aprovador provisionada separadamente da chave G114.

`labs/a190/g115_public_witness_outbox_guard_lab.py` tornou a prova de inscrição **obrigatória** tanto na criação quanto na primeira tentativa. Sem prova, alteração de campo, evento diferente, assinatura inválida ou aprovação expirada não existe autorização. No código de testes `labs/a190/test_g115_cross_process_outbox_guard_lab.py`, a segunda chave privada de teste é criada pelo próprio harness e NÃO pode ser usada em produção. Cenários históricos de assinatura/timeout agora usam a prova original adequada.

## Provas GREEN

[GitHub Actions G120 40392570322](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40392570322), código de segurança do último commit **`3aadc19e2378d06d9ee9566f9b07987aa6d41dc8`**:
- **Windows:** 30/30 PASS G120 (incluindo G115 herdados), 34/34 G118, 24/24 G116.
- **Ubuntu:** 30/30 PASS G120, 34/34 G118, 24/24 G116.
- A descoberta unittest também executa casos herdados de G115 mais de uma vez. 30 execuções G120 não são 30 controles únicos.
- Os oito novos marcadores G120 incluem rejeição de nova identidade sem prova, assinatura corrompida, outro assinador, alteração de escopo/política/ação/nonce, validade vencida NO MOMENTO DO USO, janela longa demais, falta de pin/prova/relógio, e teste deliberado de repin da raiz.
- Nenhum caso foi xfail/skip/waived; os testes RED não foram removidos.

## LIMITAÇÃO EXTERNA CONCRETA, ainda explorável

`G120_HOST_CONTROLLED_OWNER_REPIN=STILL_VULNERABLE_NOT_P0`: o teste substitui **simultaneamente** o assinador de "aprovação original" e a chave pública fixada, criando outra autorização assinada para um evento novo. Com ambas as chaves sob controle da mesma máquina, o guard aceita a operação e aciona o adaptador falso. Isso demonstra que G120 apenas prova consistência criptográfica com o pin fornecido, NÃO origem humana confiável.

A identidade real do proprietário, credenciais, consentimento, root externo, evento imutável fora do host, custódia monotônica, VFS SQLite e escrita antirollback A184 permanecem sem homologação. A própria G115 continua apresentando o bypass de restauração do ledger do custodiante na mesma máquina. Um sistema real necessitará aprovisionar/ancorar a chave de aprovação e a inscrição do evento fora do domínio administrado pelo AION.

## Próxima validação

G121 Draft #1611 reexecuta as suítes canônicas originais de Quality, Security, pip-audit/Bandit em Windows e Ubuntu sobre o SHA G120 sem alterar seletores; resultados devem ser consultados separadamente.

**0/6 P0 HOMOLOGADAS · HARD NO-GO · LAB/DRAFT ONLY · NO MERGE/DEPLOY/WORKER/REAL SEND/FUNDS.**
