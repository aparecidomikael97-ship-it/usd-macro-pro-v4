# A221 — Protocolo de comprovação independente: projeto do ensaio, **não evidência**

**Status:** PR Draft de laboratório, pesquisa e schema sem execução externa. **HARD NO-GO · 0/6 obrigações P0 externas homologadas · UNCERTAIN=ZERO_AUTO_RESEND.**

A220 simulou 13 tentativas de ataque a controles apenas hipotéticos. O A221 responde à pergunta **“que prova precisaríamos, emitida por quem e verificada como, antes de acreditar nesses controles?”**. Não seleciona, contrata, aciona, autentica ou contata custodiantes, instituições, KMS/HSM, auditor, testemunhas nem corretora. Nenhum desafio foi executado de verdade.

## Protocolo operacional futuro (apenas especificação)

Para um controle ser candidato à homologação futura, um processo **externo e separadamente autorizado** precisará demonstrar:

1. **Origem/identidade:** identificar titular/organização/chave pública e suas permissões por canal fora do host e fora do seu administrador; não aceitar “independent_verified=true” em JSON local.
2. **Desafio controlado:** definir intento, nonce, intervalo, escopo owner/tenant/workspace, permissões e ações proibidas, com execução em ambiente seguro e aprovação humana específica.
3. **Prova negativa:** capturar negações reais a tentativas do host comprometido (ex.: `Sign`, editar política ou assumir papel), e verificar que não havia rota alternativa/grant/papel delegado.
4. **Integridade/observação:** confrontar registros e checkpoints assinados/validados por fonte e testemunha com controles independentes do host; verificar inclusão, sequência, rollback, retenção e possível desligamento dos logs.
5. **Resultado e reconciliação:** comparar efeitos com consulta autoritativa da instituição financeira; assinatura da raiz, log de KMS ou ACK local **não comprovam** execução de ordem.
6. **Aceite:** evidência com data, escopo, expiração, responsável, contraprova, revisão de risco e decisão explícita do proprietário. A decisão é processo separado; nenhum mecanismo A221 oferece `may_confirm`.

## Mapa de requisitos A221 ligado aos 13 ataques A220

A tabela aponta **papéis nominais**, não pessoas ou empresas contratadas. Todos continuam `UNASSIGNED`/`UNVERIFIED`.

| Controle exigido | Fonte nominal futura | Desafio/prova futura |
|---|---|---|
| Material privado offline fora do host | Testemunha de custódia offline | Teste negativo de acesso a chave e a todos os backups |
| Custodiante offline fora do host | Testemunha de custódia offline | Tentativa de suplantação/assinatura sem presença e sem aprovação |
| Host sem `kms:Sign` | Auditor de políticas KMS | Negação de `Sign` para credencial/papel do host |
| Host sem editar política | Auditor de políticas KMS | Negação de mutação de política/grant |
| Host sem assumir papel assinante | Auditor de políticas KMS | Negação de escalada e delegação de privilégio |
| Aprovação fora do host | Auditor de aprovação do titular | Origem real e anti-falsificação do aceite out-of-band |
| Separação de poderes | Auditor de papéis | Ensaio de colusão e permissões conflitantes |
| Checkpoint externo de nonce | Testemunha anti-replay | Duplicata, nonce velho e ordem de sequência |
| Checkpoint de revogação | Testemunha de revogação | Uso de chave revogada/replay após rotação |
| Log fora do host | Testemunha independente de log | Prova de inclusão/consistência, perda de registros e fork |
| Falha fechada no outage | Revisor de risco externo | Queda/ACK perdido sem reenvio automático |
| Recibo financeiro independente | Auditor de recibo do provedor | Recibo final e consulta autoritativa vinculados à intenção |
| Isolamento owner/tenant/workspace | Auditor de escopo independente | Tentativa de troca de tenant, owner ou workspace |

O schema A221 conserva **modelo de escopo** de cada requisito: 2 `OFFLINE_ONLY`, 3 `KMS_HSM_ONLY`, 8 `BOTH`. Qualquer divergência dos controles do A220 invalida a comparação; cobertura significa **requisitos escritos**, não testes externos concluídos.

## Atenção ao log e às assinaturas

- Uma API KMS pode registrar eventos de uso e administração. Isso não basta se o host controla o logging, a retenção, as permissões de escrita/apagamento ou a fonte do checkpoint.
- A documentação oficial da AWS afirma que habilitar a entrega de digest de integridade no CloudTrail **não faz a validação automaticamente**; será preciso validar registros/digests e custodiar evidências fora do domínio comprometível.
- Logs de KMS e assinaturas válidas provam atividades criptográficas **sob uma identidade**, mas não confirmam um efeito financeiro na corretora. A prova financeira deve vir da fonte autoritativa do provedor, com consulta de reconciliação.
- “Duas testemunhas” sob o mesmo host, conta ou administrador **não são independentes**. Sem segregação demonstrada, o estado correto é **não verificado**.
- Revogação e recuperação também requerem prova monotônica de estado anterior; caso contrário, um registro antigo pode ser reapresentado.

Fontes técnicas oficiais:
- AWS KMS CloudTrail: https://docs.aws.amazon.com/kms/latest/developerguide/logging-using-cloudtrail.html
- AWS CloudTrail log file integrity validation: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html
- Google Cloud KMS audit logging: https://docs.cloud.google.com/kms/docs/audit-logging
- AWS KMS key access policies: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
- Google Cloud KMS separation of duties: https://docs.cloud.google.com/kms/docs/separation-of-duties

## Implementação restrita A221

- `labs/a221_independent_evidence_blueprint.py`: validador puro, sem I/O, cruza os 13 controles `SCENARIOS` do A220 com papel de origem e tipo de desafio fixos.
- `labs/test_a221_independent_evidence_blueprint.py`: 40 testes negativos de permissões falsas, identidade/reviewer, contato, orçamento, falha de escopo, chaves JSON duplicadas e repetibilidade.
- Workflow em Ubuntu e Windows executa 40 novos + 430 regressões A202–A220 = **470 testes por sistema operacional**, com dependências e actions pinadas.
- Um catálogo completo retorna apenas `BLUEPRINT_SHAPE_COMPLETE_EXTERNAL_AUTHORITIES_AND_PROOFS_ABSENT`. Checksum SHA-256 vincula o rascunho local, **não é assinatura nem prova externa**.
- Independentemente da entrada: `independent_root_verified=False`, `independent_witness_verified=False`, `owner_approval_valid=False`, `external_p0_homologated=0`, `may_collect_evidence=False`, `may_contact_provider=False`, `may_run_external_challenge=False`, `may_provision=False`, `may_sign=False`, `may_connect=False`, `may_confirm=False`.

## Próximo gate humano

O proprietário poderá, em uma etapa futura específica, designar o modelo e **aprovar separadamente** responsáveis, locais, contratos, custos, regras de acesso e um teste real **sem efeitos financeiros**, após análise de risco. A221 **não** solicita nem presume essa autorização.

**Fim A221: protocolo ainda sem executores e sem evidência. HARD NO-GO · P0 0/6.**
