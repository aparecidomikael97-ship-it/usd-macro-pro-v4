# AION G119 — Evidência sintética do fornecedor separada da custódia

**Data:** 2026-10-26. **PR Draft:** #1613, baseada na G118 #1608. Código testado SHA `cb646dd59ee1f97342ca5bdb24e0b9fa640e365d`. **LAB, sem integração a fornecedor real; 0/6 P0 HOMOLOGADAS, HARD NO-GO.**

## Necessidade

G118 comprova apenas que o testemunho registrou uma **reserva de intenção**. Não podemos inferir que o provedor recebeu, executou ou rejeitou a ação. Um protocolo futuro precisa separar a raiz e o domínio de assinatura do custodiante da raiz e do domínio do próprio fornecedor, sem usar qualquer assinatura do primeiro como substituto do segundo.

## Implementação LAB

`labs/a190/g119_provider_evidence_separate_root_lab.py` define uma observação independente, **somente de leitura**, com:
- Chave pública Ed25519 de teste distinta do pin G114. Construtor recusa reutilizar a mesma chave do custodiante como se fosse chave do fornecedor.
- Mensagem com esquema próprio `AION:G119:SYNTHETIC_PROVIDER_STATEMENT:V1` e domínio criptográfico `AION:G119:PROVIDER_STATEMENT_SEPARATE_DOMAIN:V1`, sem reutilizar assinaturas do custodiante.
- Desafio aleatório de uso único: o mesmo challenge é consumido mesmo se a resposta for inválida; não é possível reutilizá-lo para aprovar resposta antiga.
- Vínculo exato de evento original, SHA256 semântico, efeito, idempotência técnica, owner/tenant/workspace e sequência de reserva **observada novamente** por G118 com assinatura G114.
- `provider_event_ref` validado, claims `EXECUTED`, `REJECTED`, `PENDING` em fixture sintética, recusa de schemas, issuer, chaves, sequência e assinaturas divergentes.
- Resultado `ProviderEvidenceAssessmentLab` imutável, com `verified_real_provider=False`, `provider_outcome=UNKNOWN`, `allow_send=False`, `allow_retry=False`, `may_mark_provider_confirmed=False` em TODOS os casos — inclusive quando a declaração de teste possui assinatura matemática válida e `provider_claim=EXECUTED`.

**Importante:** a assinatura 'do fornecedor' nesta fase é gerada por uma chave privada controlada pelo próprio TESTE na mesma máquina. Ela comprova apenas o contrato técnico, não uma declaração de fornecedor externo. Não se deve marcar um Outbox real como CONFIRMED com esses dados.

## Evidência CI

[Run G119 40410645669](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40410645669), **dois jobs SUCCESS**:

| SO | G119 + herdados | G118 + herdados | G116 + herdados |
| --- | ---: | ---: | ---: |
| Ubuntu | **34/34 PASS** | **34/34 PASS** | **24/24 PASS** |
| Windows | **34/34 PASS** | **34/34 PASS** | **24/24 PASS** |

Há **12 testes G119 novos**, mais 11 métodos G115 herdados, e a descoberta `unittest` executa o grupo base também; 34 execuções não são 34 cenários novos. Os testes demonstram claims sintéticos EXECUTED/REJECTED/PENDING sem liberar operações, rejeição de assinatura do próprio custodiante e outro domínio, desafio reutilizado, troca de identidade/campo/seq, ausência de reserva assinada, rollback local, payload falso, repin de raiz e perda de ACK. O conhecido `G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0` permanece demonstrado.

## Não homologado

O assinador de teste 'fornecedor' e o assinador do custodiante estão ambos sujeitos à mesma administração. A origem original continua inscrita por fixture. Não existe confirmação de provedor real, pin provisionado fora do host, ledger externo monotônico e resistente a restore, H0 homologado, atestação native SQLite VFS ou proteção same-inode de escrita.

A G120 PR Draft #1614 foi criada para executar novamente as seis suites canônicas (Quality, Security e auditoria de dependências em Ubuntu/Windows) no código G119. **Não inferir verde antes do encerramento do CI.** A184 continua com cinco exigências externas objetivamente pendentes.

**0/6 P0 HOMOLOGADAS, HARD NO-GO. Sem merge, deploy, Worker, SEND real, contratos ou fundos.**
