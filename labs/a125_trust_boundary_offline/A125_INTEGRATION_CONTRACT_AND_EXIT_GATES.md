# AtlasQuant AION — A125 | Contrato de matrícula externa e exclusividade do emissor

**Data:** 16/10/2026. **Estado:** laboratório 100% OFFLINE / protótipo de interface de confiança / **HARD NO-GO**. **Nenhum P0 homologado**. Este contrato é uma especificação proposta; NÃO é integração com AWS, Google Cloud, Cloudflare, Twilio, OneSignal ou um serviço externo de custódia.

## 1. Problema objetivo e evidência herdada

A124 demonstrou três caminhos de ataque contra `SimulatedSurvivingWitness` no mesmo processo: restaurar memória, substituir o testemunho e contornar o wrapper chamando diretamente o emissor. A125 trata *apenas a definição da fronteira e o comportamento sintético* para substituição / bypass; não altera `atlasquant_aion_*`, nem move credenciais reais.

A125 RED isolado: verificação da assinatura **depois** de invocar o emissor fictício negou o recibo adulterado, mas `MockProvider.sent` já continha 1 chamada. O teste falhou com `AssertionError: 1 != 0`. Este é o motivo de **validar o custodiante e a matrícula antes de qualquer chamada**, além de atestar o recibo posterior. Um teste local não prova mTLS, identidade de conta ou proteção real de chaves.

## 2. Fronteiras exigidas, nenhuma implementada de verdade

```text
HUMAN_OWNER (cerimônia física/out-of-band, NÃO implementada)
    |
    +--> Matrícula imutável: issuer/verifier/endpoint/resource/tenant/epoch
    |       fora do arquivo GitHub, backup, Windows e ADMIN do AION
    |
    v
AION cliente SEM tokens do provedor; prepara pedido com binding exato
    |
    | desafio aleatório do cliente e atestação verificável do custodiante
    | falha: DENIED/UNKNOWN, NUNCA endpoint alternativo ou bypass
    v
Custodiante externo, admin e chaves independentes
    | CAS linearizável + marca ISSUE_ONCE monotônica, nonce e audit
    | antes de qualquer acesso a credenciais de envio
    | recibo de reserva != entrega/COMMITTED_EFFECT/NO_EFFECT_FENCED
    v
Emissor privado do custodiante, token do fornecedor inacessível ao AION
    |
    v
Fornecedor real (NENHUM MATRICULADO); filas/retries e late effects fora
 do alcance desta simulação
```

**Independência necessária:** AION não pode alterar pin de endpoint, copiar/ver/usar chave de assinatura, administrar restauração da custódia, obter chave/token do provedor ou iniciar envio por qualquer caminho secundário (SDK, URL, Worker, conta cloud, failover, fallback/backup). Não basta esconder variável com underscore Python.

## 3. Contrato de dados (todos os campos do laboratório são falsos)

**Matrícula assinada/registrada pela autoridade externa (proposta):**
`enrollment_id`, `policy_version`, `owner_id`, `tenant_id`, `workspace_id`, `provider_account`, `endpoint_origin`, `witness_id`, `issuer`, `public_key_fingerprint`, `key_id`, `epoch`, `expires_at`, `revoked_at`, `trust_anchor`, `monotonic_seq`, `administrative_account_id`, `audit_root`, `rotation_policy`.

**Intenção imutável:** `logical_intent_id`, `owner_id`, `tenant_id`, `workspace_id`, `provider_account`, `action`, `payload_digest`, `recipient_digest`, `epoch`, `nonce`, `deadline`, `idempotency_scope`. Não aceitar identidade ou verificador autoafirmados no próprio JSON do checkpoint.

**Recibo de admissão proposto:** `ISSUE_ONCE_RESERVED`, `UNKNOWN`, `intent_binding`, `issuer`, `key_id`, `witness_id`, `endpoint`, `seq`, `nonce`, `prior_head`, `signature`, `source_ref` verificada e zero bits afirmativos de entrega/não-efeito. O recibo precisa ser recuperável de fonte independente, com cadeia/alta-water; resposta perdida não autoriza retry.

**Operações de um serviço futuro (não implementadas):** `read-pinned-enrollment` (canal confiável), `attest(challenge)`, `prepare`, `issue-once`, `inspect-receipt`, `pre-fence` antes do handoff, `rotate/revoke` mediante cerimônia independente. `NO_EFFECT_FENCED` pós-handoff requer prova do fornecedor e não é inferível de `pre-fence` local. Identidade do provedor/conta e retenção de operações precisam ser auditáveis.

## 4. Semântica de segurança

- Atestação de identidade **antes** do `issue-once`; falha → deny sem acesso ao emissor. Uma resposta assinada depois do envio não desfaz o efeito.
- Um intento lógico / escopo / payload / destino tem binding imutável. Divergência, replay, nonce, epoch, issuer, endpoint, assinatura, tenant ou política → DENIED/UNKNOWN; jamais realocar ao cliente errado.
- `ISSUE_ONCE` é comprometido **antes** de invocar emissor. Crash no meio → `UNKNOWN_CONSUMED`, sem nova tentativa automática, sem marcar falha terminal ou limpar fila.
- O emissor tem credencial exclusiva de origem independente, protegida por IAM/egress e logging. Provar negação com credenciais reais AION, NÃO apenas com `MockProvider`.
- Confiança e recusa de retry não vêm do hash local, WORM de brinquedo, `HMAC` no mesmo processo ou flag `enrolled=True`. A autenticidade da fonte do checkpoint F1/T1 e F2 HUMAN_OWNER são provas adicionais, separadas de H0.

## 5. Evidências reproduzidas em 16/10/2026 — leitura precisa

- RED proposital: `red_baseline.py` — **1 FAIL** porque a verificação de identidade pós-envio detecta fraude tarde demais.
- GREEN: `test_contract.py` — **29/29 executados sem erro**, dos quais **25 exercitam invariantes** sob pressupostos da fixture e **4 são contraexemplos que passam ao demonstrar que o ataque funciona**: #26 token do fornecedor roubado, #27 custódia restaurada, #28 chave HMAC roubada, #29 chamada direta contornando o pin de tenant do cliente.
- Identidade falsa com metadados idênticos **mas sem chave da fixture** é recusada antes da chamada (#10); suspeita de identidade trocada por outro endpoint é recusada antes da chamada (#09). Race com **32 threads** no mesmo processo resulta em uma FakeProvider send, não 32 hosts/processos e não CAS cloud.
- Regredir A124 31/31 e A123 38/38, mas ambos incluem *casos em que PASS significa ataque bem-sucedido*. Nenhum CI hospedado/Windows do HUMAN_OWNER/POC cloud/fornecedor real foi testado.

### Quatro contraexemplos A125 — TODOS OPEN

| ID | Capacidade do atacante simulado | Resultado | Prova real que falta |
|---|---|---|---|
| A125-26 | Lê credencial interna do `MockProvider` | Envio fictício direto, ignorando custodiante | Credencial inacessível ao AION por IAM / isolamento / egress |
| A125-27 | Restaura estrutura em RAM da custódia | Emissão fictícia duplicada | Alta-water e histórico imutável, administração segregada |
| A125-28 | Obtém segredo de assinatura HMAC local | Aceita witness substituto com os mesmos metadados | Verificador/chave ancorados fora do domínio AION; rotação out-of-band |
| A125-29 | Invoca o custodiante diretamente, fora do `PinnedClient` | Passa intenção de outro tenant na fixture | Identidade real mTLS/OIDC e autorização **no servidor** |

**Importante:** a A125 não é uma solução de segurança pronta. O código usa HMAC, `RLock` e objetos Python todos sob o mesmo processo/administrador; os pins são injetados por um construtor local, não por uma cerimônia física. São limitações estruturais, não avisos cosméticos.

## 6. Portas de saída para uma futura POC real (todas NÃO EXECUTADAS)

- [ ] **G01** Pessoa/conta operacional administradora da custódia independente do AION, segregada de backup/restore/chaves; provas IAM e política de incidente.
- [ ] **G02** Inscrição HUMAN_OWNER física/out-of-band e verificador/issuer/key fingerprint fixados no cliente por canal independente; sem troca silenciosa, rollback ou fallback.
- [ ] **G03** mTLS/identidade IAM do solicitante; autorização owner+tenant+workspace+resource no **servidor**, jamais só no `PinnedClient`.
- [ ] **G04** Nenhum segredo do fornecedor ou credencial de envio no runtime AION, CI do aplicativo, Windows local ou Worker; demonstrar todos os bypasses reais negados.
- [ ] **G05** Marca ISSUE_ONCE persistida antes da chamada, CAS linearizável cross-host, alta-water auditada/imutável e sem restauração possível pelas credenciais AION.
- [ ] **G06** Recibos assinados e frescos sob custódia externa; nonce/epoch/head/tenant/digest vinculados e verificáveis em recovery/rotação/revogação.
- [ ] **G07** Transações entre DB↔WORM↔assinatura↔provedor possuem matriz de crash; estado ambíguo UNKNOWN não libera retry.
- [ ] **G08** Reprovar 32+ concorrentes cross-host, crash/power loss, co-rollback do AION e tentativa de restaurar custódia a partir da conta AION.
- [ ] **G09** Qualificação específica do fornecedor H0 para `COMMITTED_EFFECT` e `NO_EFFECT_FENCED` pós-handoff; sem prova ⇒ estado permanentemente incerto.
- [ ] **G10** Provas separadas F1/T1 da fonte externa do checkpoint, F2 consentimento físico HUMAN_OWNER, isolamento tenant e cadeia de custódia.
- [ ] **G11** CI Linux/Windows no SHA exato, autenticação/certificados reais, revisão de pentest, logs, retenção, política LGPD e proteção contra abuso de admin.
- [ ] **G12** FinOps: custos totais atuais auditados, cotação real e estimativa de pior caso; permanecer sob teto de referência R$200/mês, sem serviço/pagamento antes de autorização.

## 7. Próxima ação condicionada

Sem autorização para uma POC cloud/conta externa: preparar apenas a cerimônia de enrollment, diagrama de papéis IAM e procedimento de avaliação de custo, em documento. **Não abrir novas camadas de simulação fingindo que constituem independência física.** Provas externas F1/T1/H0/F2 seguem OPEN.

**Checkpoint:** A118 Draft #1326 não mergeada; `main` no início A125 = `5744b2b7b17c84331e6f27c569064993ff587782`; 84 históricos Quality A118 (50 FAIL +34 ERROR, Outbox 23/Saga 9 ERROR) ainda OPEN, sem execução nesta etapa; 0/6 P0 homologados, 20/20 instalação bloqueada. Worker OFF; HARD NO-GO; ZERO_AUTO_RESEND; R$0 gastos novos.
