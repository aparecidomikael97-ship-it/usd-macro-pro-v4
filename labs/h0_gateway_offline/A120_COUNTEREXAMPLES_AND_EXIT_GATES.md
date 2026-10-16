# A120 — H0-GW-01: contraexemplos que exigem custódia independente

**Data:** 2026-10-16 · **Estado:** CINCO LACUNAS ABERTAS, NÃO CORRIGIDAS · **HARD NO-GO**

## Escopo honesto

Esta rodada usa **exatamente `gateway.py`, `test_gateway.py` e `test_witness_hardening.py` da A119**, mais `test_a120_independent_custody_gaps.py`. Não modifica o Núcleo, Outbox, Saga, Worker ou o gateway A119. `FakeAdapter` não tem rede e não envia mensagens; a testemunha `SimulatedHighWater` é um dicionário mutável **no mesmo domínio de administração** do SQLite. A política `good_policy()` é uma premissa de laboratório, não matrículas de produtor ou prova jurídica/física.

### Evidência executada em Python 3.13/Linux

```
python -m unittest discover -s labs/h0_gateway_offline -p 'test_*.py' -v
Ran 29 tests — OK
```

**Como interpretar o resultado:** 24 testes anteriores continuam OK; os **cinco novos testes passam porque conseguiram reproduzir ataques**. São **5 contraexemplos OPEN**, NÃO cinco proteções corrigidas. O arquivo `A120_test_results.log` preserva o resultado; houve avisos não bloqueantes de `ResourceWarning` SQLite e `DeprecationWarning` do `fork` em processo multithread. Nenhum teste CI Windows/GitHub Actions executado nesta rodada.

| ID | Pré-condição de ataque simulada | Resultado observado (DEFEITO ABERTO) | Saída necessária |
|----|----|----|----|
| A120-01 | Restaurar **juntos** SQLite e dicionários `values/commitments` do witness antes do `ISSUE_ONCE` | Segundo `FakeAdapter.call()` para a mesma identidade: **2 chamadas** | Alta-water e compromisso duráveis sob custodiante que o processo AION/backup não possa restaurar |
| A120-02 | Depois do primeiro fake send, alterar `witness_required=0`, rearmar row `PREPARED` e abrir sem witness | Segundo fake call aceito: **2 chamadas** | Política de matrícula/obrigatoriedade fora do banco, fail-closed quando fonte independente não acessível |
| A120-03 | Depois de emitir, excluir a linha `ISSUE_ONCE` da tabela `audit` sem alterar row `intents` | `inspect()` retorna `UNKNOWN`, sem perceber que o histórico desapareceu | Prova de log/audit encadeada ao compromisso externo e a alta-water |
| A120-04 | Excluir nonce da tabela `seen_nonces` após recibo; criar novo recibo assinado de laboratório para outra intenção com o mesmo nonce | Nonce global reutilizado e aceito no laboratório | Ledger de replay fora do rollback local e política de unicidade/domínio formal |
| A120-05 | Trocar evento `ISSUE_ONCE` por `FAKE_NO_EFFECT_FENCED` na tabela `audit` | `inspect()` segue aceitando estado de row; evento falso não é detectado | Testemunha externa de histórico, não apenas hash da row |

## F1/T1 versus H0: duas provas que não se substituem

**F1/T1 — origem do checkpoint e antirollback.** Verificar identidade autenticada obtida fora do payload, vínculo `owner/tenant/workspace → repo/branch/path`, número/compromisso monotônico e recusa de restores; acesso e escrita do usuário que controla AION NÃO podem recriar a alta-water. `git sha` ou checksum local não bastam.

**H0 — efeito externo causal.** Custodiante independente precisa fornecer CAS transacional `PREPARE ↔ ISSUE_ONCE ↔ PRE-FENCE` com identidade imutável e credencial de envio exclusiva; marker durável *antes* de chamar o fornecedor, nenhuma retransmissão depois de timeout; recibo genuíno de fronteira positiva **ou** `UNKNOWN` permanente. **`NO_EFFECT_FENCED` pós-handoff não é demonstrável pelo gateway isolado:** exige prova do lado do fornecedor que abranja filas, carrier, retries e efeitos tardios. Não converter `queued`, `200`, `404`, callback `FAILED`, TTL ou cancelamento em ausência definitiva de efeito.

**F2 — HUMAN_OWNER.** Consentimento/autenticação físico e autorização para ações críticas são gates separados que também continuam pendentes.

## Contrato mínimo de aceitação futura (não realizado)

1. Identidade do custodiante, chave de verificação confiável out-of-band e permissão de leitura/escrita demonstravelmente fora da administração do AION; matriz de separação de deveres.
2. Um compromisso de `intent identity + row + audit-head + nonce/replay epoch + version + scope` assinado/confirmado externamente antes de efeitos; prova de incremento atômico comparável sob corrida de 32+ contendores e restauração adversária.
3. `witness-required` e autorização para enviar obtidos de enrollment externo, não de SQLite ou de `SimulatedPolicy`.
4. Ensaios físicos/distribuídos: rollback isolado, co-rollback, chave revogada, testemunha offline, split-brain, restore simultâneo, concorrência, perda de resposta, atraso de callbacks e failover; somente em sandbox externo aprovado e sem enviar a clientes.
5. Qualificação separada de cada fornecedor antes de alegar prova H0 de não efeito tardio; se não houver fence causal, aceitar apenas o contrato ONE-SHOT + `UNKNOWN`/quarentena e **NÃO** afirmar exactly-once delivery.
6. Evidência de CI Linux/Windows no HEAD exato, inspeção independente e autorização específica antes de qualquer produção. Não gastar nem criar contas nesta etapa.

## Auditoria estática da fonte produtiva (A118, NÃO teste dinâmico)

Revisada diretamente por GitHub connector em A118 HEAD `c62fab663c6349d7320f7843c8d09587c514426b`:
- `atlasquant_aion_global_worker_inflight_reconciliation.py` blob `94e127b2ade4bc9ae673073cc8f00a6623297891`: `_receipt_is_safe` exige os quatro bits de segurança explicitamente `False`/`bool`; recibos terminais/FAILED persistidos no checkpoint recebem classificações **LOCAL_*_UNVERIFIED**, não `*_PROVEN`; `automatic_clear_allowed=False` e `automatic_retry_allowed=False` nas saídas; `terminal_proven=0`, `failed_proven=0` ainda sem produtor independente.
- `atlasquant_aion_global_worker_inflight_resolution.py` blob `9d098534d66f0a2ecc7a58bed24ff3021c834749`: operação de limpeza é **apenas estágio em memória**, exige confirmação e status elegível; **não** foi executada nem avaliada dinamicamente neste ciclo.

Esse exame de código fonte reduz incerteza sobre **a lógica estática de negação**, mas não certifica que todos os caminhos operacionais estão à prova de adulteração/integração nem substitui testes dinâmicos com dependências produtivas.

## Estado após A120

- **ZERO** correções de produção; zero merges, PR nova, deploy, Worker, mensagens, contas, gastos ou acesso ao Windows.
- **0/6 P0 homologados; 20/20 FIRST_INSTALL BLOCKED.** Último A118 Quality relatado: **84 diagnósticos históricos OPEN (50 FAIL + 34 ERROR)** e não reexecutados aqui. A matriz da issue #1323 documenta a linha mais antiga A115 de **89 ocorrências**; essas bases têm cortes distintos e não devem ser somadas.
- Recomenda-se **parar de fortalecer a mesma testemunha em RAM** como se isso aproximasse a homologação: a próxima entrega realmente necessária é um mecanismo de custódia fora do domínio de falha da máquina e conta do AION, sujeito a autorização e avaliação de custos.
