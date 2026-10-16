# A121 — ADR: Custódia independente para H0 e F1/T1, sem aprovar produção

**Data:** 16/10/2026 · **Decisão:** contrato e auditoria experimental em laboratório, não homologado · **Prioridade:** P0 do Núcleo AION.

## 1. O que realmente precisamos comprovar

No A120, o SQLite e a `SimulatedHighWater` de RAM eram controlados pelo mesmo backup/administrador: restaurá-los juntos permitiu **outra chamada fictícia**. A forma correta de obter independência **não é mudar o nome da classe para ExternalWitness ou trocar de banco**. É demonstrar separação real de quem administra a custódia, quem detém as credenciais do fornecedor, quem pode restaurar histórico e de onde vem a chave de verificação.

A arquitetura de destino (NÃO implementada) requer **três fronteiras distintas**:

```text
AION local (checkpoint / mirror; nunca possui credencial de emissor)
    |
    | pedido para intenção imutável + escopo autenticado por canal externo
    v
Custodiante externo sob administração separada
    | matrícula independente owner/tenant/workspace/resource
    | CAS linearizável PREPARE ↔ ISSUE_ONCE ↔ PRE-FENCE
    | marca ISSUE_ONCE DURÁVEL ANTES de emitir
    | trilha de auditoria/nonces + proof assinada com chave externa
    v
Agente de envio com credenciais exclusivas desse custodiante
    |
    v
Fornecedor da ação irreversível
```

**H0 pós-handoff:** mesmo um custodiante completo, com um único `ISSUE_ONCE`, **não prova** que mensagem já enfileirada no fornecedor nunca será enviada, nem confirma entrega ao destinatário. Sem apoio do fornecedor para cancelamento/fence causal abrangendo atrasos/retries, o resultado continua `UNKNOWN`. `ZERO_AUTO_RESEND`.

**F1/T1:** provar origem e monotonicidade do checkpoint é questão separada da prova de envio; mesmo uma futura solução H0 não torna o checkpoint autêntico por consequência. **F2/HUMAN_OWNER físico** também permanece separado.

## 2. Diferenças entre a fixture A121 e a custódia real

| Tema | Fixture offline A121 | Aceite para custódia de verdade |
|---|---|---|
| Administração | Dois SQLite no mesmo Linux, mesmo usuário | Conta/organização administrativa externa; restaurar AION não pode alterar custódia nem chaves |
| Emissão | `FakeSender` no mesmo processo, sem rede | Credenciais do fornecedor inacessíveis ao AION e exclusividade testada, incluindo caminhos alternativos |
| Identidade | `Intent` imutável passado pelo chamador | Autenticação e autorização de tenant/recurso/owner por canal independente, não self-assertion |
| Matrícula | Flag `enrolled=True` mockada | Matriculação auditável por HUMAN_OWNER via fluxo independente; revogação/rotação |
| Atomicidade | Transação SQLite `BEGIN IMMEDIATE` | CAS com semântica linearizável demonstrada em HA/failover/32+ concorrentes |
| Persistência | Ledger em arquivo local | Custódia durável monotônica, backup/restauração que não permita apagar ISSUE_ONCE |
| Prova | `sha256` local / nenhuma assinatura externa | Atestação autenticada de origem e freshness com chave distribuída out-of-band e anti-replay |
| Auditoria/nonces | Corrupção isolada detectável | Trilha independente retida e verificável; abuso de admin e restore também bloqueados/detectados |
| Resposta perdida | `UNKNOWN`, não reenviar | Mesmo contrato com reinício, timeout, 429, 5xx, split-brain e reconstituição do processo |
| Prova negativa | PRE-FENCE **somente antes** da emissão fictícia | H0 `NO_EFFECT_FENCED` pós-handoff somente se fornecedor provar abrangência real de filas, retries e canais |
| Preço | R$ 0, mock local | Limites de custo mensuráveis, aprovação prévia, teto do projeto respeitado |

## 3. Testes executados (o que demonstram)

- **A121 23/23 PASS** em Python 3.13/Linux. Testes 01–22 verificam a lógica de negação **sob as hipóteses do laboratório**: persistência da fixture não restaurada, autenticação simulada e ausência de SDK real. Inclui disputa de 32 processos com no máximo uma concessão, replay/nonce, audit hash e separação de `UNKNOWN`/pre-fence.
- **A121 #23 PASS É UM CONTRAEXEMPLO ABERTO:** backup do próprio arquivo custodiado antes de `ISSUE_ONCE`, emissão fake, restauração integral do arquivo custodiado, segunda emissão fake. Isto demonstra que até a nova fixture é contornável por administração comum — nenhum P0 fechado.
- **A120 29/29 PASS** em execução separada; 24 regressões sintéticas e cinco testes que passam por observar falhas originais A120. Não somar passagens como 52 garantias homologadas.
- Sem CI hospedada, Windows físico, emulação da rede, assinatura independente ou provedor real.

## 4. Escolha de infraestrutura — NÃO CONTRATAR AINDA

**Portas de decisão, sem escolher fornecedor antes de avaliar a fronteira de confiança:**

1. Definir proprietário/admin único e papéis de custódia independente: AION só consulta/solicita, não troca chaves, não reseta marcador, não administra backups. Responsável humano de segurança fora do runtime precisa controlar matrícula/revogação. Se tudo ficar numa única conta controlada por AION, continuar NO-GO.
2. Desenhar duas opções conceituais para cotação futura: um serviço gerenciado transacional com banco/conta e IAM externos, ou uma pequena API de custodiante com ledger sob conta separada e verificador independente. **Nenhuma é declarada segura apenas por usar DynamoDB, PostgreSQL ou Durable Objects.** Requer comprovação de privilégio, backup, rollback, quorum e durabilidade.
3. Documentar retenção, operação após expirar TTL, read-your-writes, desempenho em queda de rede, HA/failover, revogação de chaves, conta comprometida, política de restauração e custo mensal/máximo. Não registrar preços sem cotação recente e autorização.
4. Executar, em *sandbox especificamente autorizado*, ensaio `issue_once` → snapshot do AION → restore do AION → tentativa repetida ⇒ **negada pela custódia remota**; em paralelo, tentativa de restore do custodiante por credenciais AION ⇒ **acesso negado**. Exigir evidência de IAM/log de contas e chaves independentes.
5. Antes de qualquer envio real, qualificar o provedor da ação e distinguir `provider accepted` / `carrier handoff` / `delivered`. Sem fence definitivo, manter `UNKNOWN` permanente após erro e não realizar auto-resend.

## 5. Critérios de saída P0 (não realizados)

- [ ] Atestação assinada com verificador/âncora fora do controle da máquina/backup AION; provedores e identidades auditados.
- [ ] Segregação de privilégios demonstrada: o runtime não restaura/substitui contador, nonce, cadeia de auditoria nem inscrição 
final.
- [ ] Histórico e alta-water permanecem válidos após rollback/co-rollback local, failover e troca de instância; administrador AION incapaz de restaurar custodiante.
- [ ] Matriz cross-host e Windows/Linux com concorrência, interrupções, TTL vencido, replay e perda de resposta; marcadores antes de tentativa externa.
- [ ] F1/T1 source binding e custodiante independente; H0 e F2 aprovados cada um com prova específica, sem substituição por simulação.
- [ ] Custo/cotas/LGPD/operador legalmente aptos, gastos expressamente autorizados pelo HUMAN_OWNER.

**Estado após A121:** 0/6 P0 homologados, 20/20 gates FIRST_INSTALL bloqueados; 84 Quality históricos A118 ainda OPEN, não reexecutados no repositório. PR A118 #1326 Draft sem merge; main/Worker/deploy sem alteração. **HARD NO-GO e R$ 0 de novos gastos.**
