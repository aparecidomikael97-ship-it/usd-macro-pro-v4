# AION P0 — plano de obtenção de evidências para homologação (SEM execução externa)

**20/10/2026. HARD NO-GO. 0/6 P0 homologados. Worker OFF. ZERO_AUTO_RESEND.**  
Este registro é uma lista de **critérios de saída verificáveis**, não autorização para iniciar serviços. O conteúdo é um complemento versionado do registro original de seis P0 de 19/10, cuja linha histórica de Quality deve ser preservada.

## Descoberta importante: dois históricos de Quality, não um só

- Registro original dos seis P0 `AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json`: snapshot anterior, **6.562 testes / 50 FAIL / 34 ERROR**, evidência histórica.
- Registro mais recente do pente-fino de Quality `AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json`: run [#39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568), **6.562 testes / 51 FAIL / 34 ERROR**, também histórico e RED, não uma nova Quality executada por este PR.
- **Diferença: +1 FAIL, 0 ERROR.** Não somar ou substituir indevidamente snapshots, nem declarar 365 Security verde.
- Os 85 casos registrados vêm de nove módulos: Outbox, Saga, Global Worker, Ativação, Verificação ao vivo, Reativação, Readiness, Execução local e a própria cobertura da Quality. **Nenhuma identidade exata de caso está atribuída como o P0 histórico original SQLite-read ou SQLite-write.** Os 32 ERROR Outbox/Saga são predominantemente negações de confiança externa e não demonstram que os dois P0 SQLite foram resolvidos.

## Ordem de trabalho, com rigor de evidência e sem gasto

| Ordem | P0 / bloqueio | Próxima evidência que realmente muda a decisão | Pode fazer sem gastar? |
| --- | --- | --- | --- |
| **1** | Compatibilidade SQLite — leitura | Descobrir **run, job, teste, stack, commit original RED** e confrontar com o caminho de leitura atual; reproduzir sem modificar asserção | **Sim:** forense nos runs/commits locais e GitHub |
| **2** | Compatibilidade SQLite — escrita | Descobrir **run, job, teste, stack, commit original RED**; reproduzir com rollback, WAL, owner-thread, nested transaction e concorrência | **Sim:** forense no GitHub + LAB offline |
| **3** | Identidade real HUMAN_OWNER | Credencial FIDO2/Windows Hello real, RP/origin, challenge, trust root/recuperação e consentimento audível por canal protegido | **Parcial:** requisitos e testes falsos. **Não** matricular identidade real automaticamente |
| **4** | Autenticidade de recibos / produtor | Matrícula independente do produtor, conta, issuer, digest/epoch e recibo `COMMITTED_EFFECT`; `NO_EFFECT_FENCED` terminal, caso suportado | **Parcial:** documentação oficial e resposta escrita do fornecedor, sem enviar mensagens |
| **5** | Primeira operação com resultado incerto | Reserva de primeira tentativa fora do SQLite, crash+timeout+recuperação, sem novo POST e garantias reais de efeito/não efeito | **Parcial:** cenários offline, protocolo e RFI, sem ativar envio |
| **6** | H0 após reinício | Conta e administrador independentes, sequência/epoch monotônicos autenticados, S3 WORM versão exata, HEAD externo fresco, power-loss real | **Parcial:** revisão IAM/FinOps/boot em LAB. **Não** provisionar AWS/Cloudflare |

As prioridades acima são de **próxima evidência obtível**, não uma afirmação de que os testes SQLite sejam mais importantes que a segurança dos outros quatro P0. Independentemente da ordem, **todos são gates obrigatórios** para ação crítica.

## Critérios de aceite exigidos para cada P0

Os contratos individuais estão na [matriz estruturada de seis P0](AION_P0_SIX_EXIT_EVIDENCE_GAP_MATRIX_20261020.json). Para cada um, exige-se identificação e revisão da fonte, caso original antes/depois quando aplicável, testes adversariais invariantes, logs imutáveis/referências Git verificáveis, execução da Quality e Security canônicas *no mesmo candidato exato*, revisão independente, identidade/autorização real do proprietário e aprovação de integração separada.

**Não contam como homologação:** teste novo verde contra mock, assinatura de fixture cuja chave está no mesmo processo, `verified=true`, resultados de API com `Message SID`/`operationId`, SQLite `CONFIRMED`, backup local, cabeçalho S3 autoafirmado, arquivo em outra conta sob mesmo administrador, RFI sem garantia contratual e correspondência temática com algum dos 85 casos Quality.

## Contratação, limites e decisões pendentes

Nenhuma matriz offline fornece autorização para ativar o Worker, reexecutar envios incertos, comprar número SMS, criar bucket Object Lock, usar Cloudflare DO, assinar KMS ou ampliar custos. O teto conhecido permanece **R$200/mês como referência**, com exceção condicionada a autorização específica. Os templates atuais de FinOps ainda têm preços, retenção e volume **não verificados**. O usuário poderá decidir contratar apenas após análise de custo real, riscos de retenção imutável e política de segregação.

A intenção atual é **não criar dependência paga desnecessária**. Dúvidas ao fornecedor podem ser reunidas em rascunhos, mas enviar e-mail ou iniciar teste externo exige decisão separada. O rascunho privado de OneSignal não integra este pacote público.

## Procedimento mínimo para encontrar as duas falhas SQLite sem inventá-las

1. Pesquisar os **runs históricos vermelhos** referenciados pelo registro dos seis P0 e o commit A118, recuperando IDs completos de jobs, nomes de testes e traces de falha, sem executar comandos de envio.
2. Localizar o teste/asserção original (inclusive renomeação no Git), verificar se o incidente corresponde a owner-thread, binding SQLite, concorrência/cursor ou nested transaction — **não atribuir família antes do stack**.
3. Preservar `RED_original` e `GREEN_candidate` com hashes, diffs mínimos e execução Ubuntu/Windows. Se o original não for localizável, deixar **UNMAPPED / OPEN**, não substituir por teste inventado.
4. Só então propor correção de código sob branch LAB, sem merge. Nunca enfraquecer proteção de transação/leitura para reduzir FAIL.

**Próxima tarefa operacional recomendada:** recuperar os logs do run histórico e completar a identificação dos dois incidentes SQLite. Se os logs tiverem expirado, registrar evidência da expiração e procurar artifacts/commits do Git; a ausência de logs não permite presumir aprovação.

**Status:** Quality canônica RED (51 FAIL, 34 ERROR no último registro); 32 ERROR Outbox/Saga `OPEN_NOT_WAIVED`; 0/6 P0; HARD NO-GO; Worker OFF; ZERO_AUTO_RESEND; sem merge, deploy, serviços externos ou gastos.
