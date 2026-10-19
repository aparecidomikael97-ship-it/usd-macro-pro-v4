# AtlasQuant / AION — Cloudflare Durable Objects como possível custodiante H0

**Revisão técnica de 19/10/2026. PROPOSTA + SIMULADOR OFFLINE, SEM CONTA OU DEPLOY.**

**Decisão presente:** **Cloudflare DO não está aprovado nem configurado como custodiante independente. 0/6 P0 homologados; HARD NO-GO; ZERO_AUTO_RESEND; AION Worker OFF.** Nenhum arquivo desta rodada é um Worker da Cloudflare ou um endpoint implantável. Não há tokens, segredo, assinatura, provedor real ou autoridade de efeito. Nenhum custo novo autorizado.

## Fontes oficiais consultadas em 19/10/2026

- SQLite Durable Objects: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/ (documentação atualizada 21/09/2026). O armazenamento privado de cada DO é transacional e fortemente consistente; `transactionSync(callback)` existe, `sql.exec("BEGIN")` e `sql.exec("SAVEPOINT")` não são permitidos. Cursors atravessando `await` podem observar estados não estáveis; consumir `.toArray()` antes de qualquer `await`.
- Limites: https://developers.cloudflare.com/durable-objects/platform/limits/ (01/06/2026). No Workers Free, DO SQLite está disponível com **5 GB por conta**, até **100 classes** (cada namespace tem objetos ilimitados). Os limites de SQL por consulta também importam: 100 colunas, 100 parâmetros e 100 KB de comando SQL. Dados de até 2 MB por linha, limite de armazenamento por objeto aplicável ao plano.
- Preço: https://developers.cloudflare.com/durable-objects/platform/pricing/ (30/09/2026). Plano Free: **5 milhões de linhas lidas/dia, 100 mil linhas escritas/dia, 5 GB de armazenamento total**; ultrapassar limites de uma classe de uso Free faz falhar operações dessa categoria. Limites de duração/requests do Workers também se aplicam. Não confundir limites com custo zero garantido em futuro plano pago.
- Recuperação: mesma API SQLite **inclui Point In Time Recovery (PITR)** capaz de restaurar dados anteriores dentro de janela de **30 dias**. Este recurso é útil para continuidade, mas **é um risco real de rollback do próprio custodiador**. Um admin com permissões sobre o objeto pode também executar `deleteAll()` ou mudar código de escrita. Mesmo forte consistência de gravação não significa monotonicidade imune ao administrador.
- Modelo de concorrência: https://developers.cloudflare.com/durable-objects/api/state/ e https://developers.cloudflare.com/durable-objects/best-practices/rules-of-durable-objects/ . Operações SQL síncronas dentro do DO não intercalam eventos, mas `await` no meio do read-modify-write pode abrir janela de concorrência; operações que exigem uma reserva atômica devem ocorrer no mesmo bloco `transactionSync`, sem `await`.

## Contrato transacional proposto para uma FUTURA implementação

Um Durable Object lógico por shard de escopo fixado, identificado **somente por servidor confiável**; nunca aceitar `idFromName()` com escopo inventado pelo caller como autorização. Conectar por binding de serviço restrito, com políticas de autenticação de máquina e tenant em outra camada. Os dados abaixo são propostas, **não interfaces expostas nem esquema instalado**.

```text
POST /reserve_intent   [não implementar até matrícula independente]
  scope_digest=sha256(tenant/workspace/action sob identidade VALIDADA)
  intent_id, intent_digest, nonce, expected_epoch, expected_sequence

transactionSync no Durable Object:
  Validar token do chamador autenticado independentemente do payload
  Ler scope_head(epoch,sequence,digest)
  Recusar versão/epoch, digest, nonce e intenção já usada
  Atualizar head CAS no mesmo bloco de transação
  Persistir tentativa ATTEMPT_RESERVED com identidade e nonce
  Commit durável conforme contrato Cloudflare
  Responder receipt com assinatura e key_id PINNED de outra autoridade
  Se resposta se perder => UNKNOWN, nunca re-reservar nem reenviar

GET /readback
  autenticar caller, refazer consulta forte do mesmo objeto
  retornar epoch/seq/digest e prova de autoria/frescor
  timeouts, falha, fork e falta de assinatura => BLOCKED
```

**Importante:** uma gravação `ATTEMPT_RESERVED` remota não garante que o prestador externo enviou ou deixou de enviar SMS, cobrança ou trade. Para desbloquear `UNCERTAIN`, exigir separadamente `effect-confirmed` ou `no-effect-fenced` terminal, autenticado pelo fornecedor. `GET` com resultado vazio em Twilio não é prova de não envio. AION não faz auto-retry de primeira operação.

Não aprovar um desenho que tenha apenas uma chave em variável de ambiente no mesmo Worker do cliente e uma assinatura gerada a partir de input local. Sem pinning de issuer/account/key e validação fora do mesmo domínio administrativo, a suposta assinatura não atesta independência.

## Falha arquitetural decisiva: PITR do custodiante

Um único DO SQLite sob uma conta Cloudflare separada pode detectar **rollback local do AION** enquanto sua própria base permanece fresca. Porém:

1. **Rollback do executor isolado:** local seq=0, DO seq=1 => divergência observável. Exige autenticação de DO para virar prova, ainda não existe.
2. **Rollback/PITR do DO isolado:** local seq=1, DO seq=0 => divergência observável. Sem uma terceira fonte independente, não se sabe qual cópia é verdadeira, logo BLOCKED.
3. **Rollback coordenado de ambos:** local seq=0, DO seq=0 => estados aparentemente coincidem. Mesmo que os hashes também coincidam, essa coincidência NÃO demonstra que o evento anterior não ocorreu. Uma assinatura do DO após seu próprio PITR também não prova que o head antigo nunca existiu. **HARD NO-GO** até existir ancoragem adicional fora do domínio da Cloudflare e do executor, por exemplo recibo de append-only/WORM de outro custodiante com administração distinta, custódia de chave adequada e auditoria independente.
4. **Credencial administrativa comprometida:** um admin pode publicar novo código, restaurar dados e produzir novos registros. A conta separada reduz risco de comprometimento conjunto, mas não elimina essa possibilidade; segregação e revogação precisam de teste e prova real.
5. **Erro de sincronismo / rede offline:** BLOCKED antes de qualquer primeira ação externa, sem fallback local que permita continuar.

**Condição de decisão:** Cloudflare pode ser um componente do protocolo, mas **um único Durable Object não é suficiente para fechar o P0 antirollback**. A separação de contas, um segundo domínio de ancoragem contra PITR e evidências externas são requisitos, não melhorias opcionais. Se isso ultrapassar R$200/mês ou exigir jornadas manuais inviáveis, a escolha permanece NO-GO; não provisionar por impulso.

## Evidências produzidas nesta rodada (somente simulador)

- `atlasquant_aion_p0_h0_custody_two_domain_model_lab.py`: SQLite local com `BEGIN IMMEDIATE` para simular reserva CAS da primeira tentativa e sequência, **NÃO Cloudflare**. Cada resultado tem `state=BLOCKED`; todas as flags `external_highwater_verified`, `custodian_identity_authenticated`, `first_effect_allowed`, `worker_arming_allowed`, `automatic_retry_allowed`, `external_action_executed` são **False** mesmo quando `MODEL_RESERVED_NOT_AUTHORITY` é alcançado.
- `test_aion_p0_h0_custody_two_domain_model_lab.py`: **20 testes** de duas conexões disputando o CAS, duplicação, nonce, resposta perdida, identidade de escopo, epoch, fechamento e retomada, rollback só do executor, só do custodiante, e ambos. Cenário ambos-rollback retorna `MODEL_HEAD_MATCH_ONLY_NO_EXTERNAL_PROOF` e permanece `BLOCKED`. Não há assinatura, nuvem, API real, custódia off-host, Key Management ou conta separada neste teste.
- `.github/workflows/aion-p0-h0-cloudflare-custody-contract-lab.yml`: CI Ubuntu + Windows para 20 novos e regressões H0, restore SQLite, mutações de gate e F1/T1/A110. Apenas arquivos de LAB; não faz deploy/Worker/provedor nem concede permissões de escrita para CI.

## Checklist de homologação futura (não atendido)

- [ ] Dono humano confirmado e autorização para separar contas e administrar witness
- [ ] Orçamento/cotas e custos projetados/reais com bloqueio automático de consumos
- [ ] Custodiante com IAM/MFA separados; confiança de issuer e chave enrolada por canal independente
- [ ] Terceira âncora imutável/durável, anti-PITR e trilha de auditoria independente de Cloudflare e host
- [ ] Implementação DO de `transactionSync` sem `await`, replay registry e CAS persistido remoto
- [ ] Readback assinado independente, freshness, revogação, nonce single-use e idempotência por intento
- [ ] Dois clientes físicos e cenário timeout após commit, race, reboot, power loss, PITR de DO e restauração de disco
- [ ] Producer receipts e terminal no-effect independente de high-water
- [ ] Wiring real ao boot, preclaim, primeiro envio e Global Worker sem bypass ou mock positivo
- [ ] Quality/Security canônicos + revisão externa, REDs originais sem supressão

**Decisão final:** DOCUMENTADO/SIMULADO EM LAB. **Custodiante não selecionado nem criado. 0/6 P0, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND.**
