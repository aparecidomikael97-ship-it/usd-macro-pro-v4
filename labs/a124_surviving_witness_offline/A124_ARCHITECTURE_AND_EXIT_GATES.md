# AtlasQuant / AION — A124: testemunha sobrevivente e exclusividade de emissão

**Data:** 2026-10-16 | **Estado:** TESTE SINTÉTICO OFFLINE / HARD NO-GO / ZERO_AUTO_RESEND | **Não é POC cloud nem homologação.**

## Objetivo e linha de base RED

Na A123, dois bancos SQLite locais (admissão + WORM de brinquedo) podem ser restaurados juntos. O teste `red_baseline.py`, executado explicitamente antes da nova proteção, terminou com **1 FAIL**: após primeira chamada ao `FakeSender`, a restauração de ambos permitiu uma **segunda chamada fictícia**, quando o contrato esperado era no máximo uma. Evidência de saída: `AssertionError: 2 != 1`. Isto não é SMS real.

## Desenho e resultado A124 (condicionado)

```text
Local AION — SQLite A123 ledger          Local toy-vault — SQLite A123
        \                                     /
         \ snapshots/restores do mesmo admin /
                       |
                       v
        GuardedAdmissionFixture (apenas wrapper de teste)
                       |
           PRE-ISSUE reserva, antes do emissor
                       v
       SimulatedSurvivingWitness (RAM, no mesmo processo)
           - index por ID lógico + digest de escopo
           - ISSUE_ONCE reservado uma única vez sob lock local
           - cadeia de hashes, nonce e assinatura HMAC FICTÍCIA
           - falso testemunho de prestador NÃO é aceito
                       |
                   A123.issue_once
                       |
                   FakeSender
```

- **A124 test 03:** snapshot/restauração conjunta de ambos os bancos SQLite é detectada pelo registro sobrevivente em RAM; segunda chamada fictícia negada. **Só vale enquanto esse objeto íntegro sobreviver**.
- O wrapper reserva na testemunha *antes* de A123 tentar chamar o emissor; se o sistema cair entre o registro e a chamada, preserva a reserva, abandona a intenção como incerta e não reenvia. Custa disponibilidade em favor de evitar uma segunda tentativa.
- Índice/assinatura e identidade de intenção são verificadas em testes sintéticos. A assinatura usa HMAC com a chave **dentro do mesmo processo** e, portanto, não estabelece procedência externa.
- `inspect()` sem registro jamais equivale a `NO_EFFECT_FENCED`. Mesmo um `ISSUE_ONCE` atestado **não** comprova envio, entrega nem ausência futura de efeito do fornecedor.

## Resultados executados (Python 3.13 / Linux)

| Conjunto | Resultado | Leitura correta |
|---|---|---|
| `red_baseline.py` isolado | **1 FAIL** | Defesa A123 inexistente diante da restauração conjunta de dois DB; reproduz 2 chamadas fake |
| `test_witness.py` A124 | **31/31 PASS** | 28 verificações de contrato/limite + **3 casos que passam ao reproduzir ataques**; inclui 32 threads sob `RLock`, NÃO 32 processos/hosts |
| `test_contract.py` A123 inalterado | **38/38 PASS** | Regressão local incluindo A123 caso 35 que passa ao reproduzir co-rollback |
| Python / warnings | **Python 3.13.5**, `-W error` | Sem avisos; sem Windows, CI GitHub ou nuvem testados |

### Três contraexemplos A124 — TODOS ABERTOS

- **A124-25: `restore_as_same_admin_for_attack` + restore dos dois bancos.** A testemunha em RAM pode ser alterada pelo mesmo administrador; segunda emissão fake ocorre.
- **A124-26: substituição do witness por nova instância com a mesma identidade assumida.** Sem endpoint pinning/identidade externa autenticada, segunda emissão fake ocorre após restore local.
- **A124-30: chamada direta de `AdmissionFixture.issue_once` após restaurar os bancos.** O guard é apenas wrapper: sem exclusividade técnica das credenciais reais do fornecedor, a segunda emissão fake é possível.

**A declaração "31/31 PASS" não fecha estes três ataques.** Também não fecha ataque em que atacante controle código/fonte, restaure testemunha, falsifique chaves HMAC da fixture ou execute bypass de credenciais.

## Contrato obrigatório de custódia remota real — portas de aceite NÃO EXECUTADAS

- [ ] **A124-G01 / independência administrativa.** Endereço e conta do custodiante atribuídos por matrícula do HUMAN_OWNER por canal independente. O administrador/runtime AION não tem permissão de restaurar, substituir, remover, reconfigurar, girar chaves ou desativar a custódia.
- [ ] **A124-G02 / endpoint e identidade ancorados.** Certificado/chave/verificador/issuer e escopo owner/tenant/workspace/repo/branch/path/epoch fixados fora do JSON/SQLite controlado pelo AION. Troca de witness/issuer é negada, inclusive em restore e rebuild.
- [ ] **A124-G03 / credenciais exclusivas do emissor.** AION não possui API token/credential do provedor; todos os caminhos (CLI, backup, cloud admin, failover, worker, integrações) são incapazes de contornar o custodiante. Demonstrar negativa real com logs e IAM.
- [ ] **A124-G04 / alta-water monotônica.** `ISSUE_ONCE`, nonce, epoch, política, histórico e cabeça assinada preservados sob custódia WORM/monotônica sem rollback ou restauração viável pelo domínio AION. Revisar restauração do próprio custodiante, desastre e rotação de chaves.
- [ ] **A124-G05 / decisão atomicamente linearizável.** Emissão com CAS centralizado, registro durável antes de qualquer acesso ao emissor, 32+ concorrentes *entre hosts*, failover, restart e cortes de rede. Perda da resposta -> UNKNOWN, zero auto-resend.
- [ ] **A124-G06 / provas autenticadas e atuais.** Assinatura independente, verificação de nonce/freshness, confirmação read-after-write, proteção contra replay, substituição da chave de validação, bifurcação de cadeias, retenção pós-TTL.
- [ ] **A124-G07 / separação F1-T1 x H0 x F2.** Fonte GitHub/tenant e antifraude de checkpoint têm fonte/owner verificáveis; H0 fornece recibo causal de efeito do fornecedor ou `NO_EFFECT_FENCED` verdadeiro pós-handoff; F2 exige confirmação física do proprietário. O witness de emissão não substitui estas provas.
- [ ] **A124-G08 / política de falhas e custos.** Indisponibilidade/degradação -> fail closed, sem bypass por flag, grace period ou conta alternativa. Testes de recuperação, LGPD, quotas, preços reais sob teto tecnológico aprovado, sem cobrança/contratação automática.
- [ ] **A124-G09 / integração autorizada e auditada.** Ensaios em Windows/Linux e hosts separados, CI do SHA exato, segurança de secrets/IAM, revisão de riscos, autorização para cada serviço e envio externo, rollback explícito sem efeito duplicado.
- [ ] **A124-G10 / precedência de segurança.** Sem evidência para G01–G09, status READY/H0/F1/T1/F2 não sobe; nenhum merge, deploy, Worker, autorização comercial ou uso com dados reais.

## Limites institucionais

A124 **não implementa** AWS DynamoDB/S3/KMS, Google Firestore/Cloud Storage, Cloudflare Durable Objects, OpenAI plugins, Windows TPM, fornecedor Twilio/OneSignal, SMS, email, payment gateway, RBAC real, assinaturas reais, autenticação independente, WORM externo, multi-tenant real, FI/antirollback físico ou No-Effect real. Toda matrícula é uma flag falsa e o atacante pode ter o mesmo sistema operacional/memória dos simuladores. A121–A123 permanecem íntegros; nenhuma função de produção foi modificada.

**Estado canônico:** última evidência A118 com 84 FAIL/ERROR históricos (50 FAIL, 34 ERROR; Outbox 23 ERROR, Saga 9 ERROR), não reexecutados nesta A124; A115 histórica distinta = 89 ocorrências. 0/6 P0 homologados, 20/20 gates FIRST_INSTALL bloqueados, Worker OFF, ZERO_AUTO_RESEND, HARD NO-GO. Nenhum custo, credencial, conta cloud, merge ou deploy.
