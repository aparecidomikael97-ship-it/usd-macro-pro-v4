# A121 — contrato experimental de custódia separada (HARD NO-GO)

**Data:** 2026-10-16. **ESTADO:** laboratório sintético de comportamento, **não é custódia externa verdadeira** e **não está integrado** ao AION.

O laboratório A120 demonstrou cinco vulnerabilidades de um registro de intenção e testemunha mantidos sob a mesma administração/backup. Este A121 faz uma **simulação de fronteira custodial**: um banco SQLite separado mantém enrollment, intenção imutável, marcação única de tentativa antes do `FakeSender`, cadeia de auditoria e nonces. Um banco/espelho local pode ser restaurado sem automaticamente desfazer a concessão da tentativa no *outro banco*.

Tudo roda na **mesma máquina/contêiner e no mesmo domínio administrativo**, com credenciais e chaves fictícias. O `CustodianFixture(enrolled=True)` **é uma hipótese definida pelo teste** e não pode, na produção, comprovar independência; a classe `FakeSender` não tem rede, canal ou credenciais. Não existe assinatura de atestação externa, hardware/TPM, repositório de chave independente, protocolo autenticado, proteção de root, alta disponibilidade, SLA, cobrança, fornecedor de SMS, prova de envio nem verificação do Windows físico.

## Testar

```bash
cd labs/a121_custody_contract_offline
python -m unittest -v test_contract
```

Executado localmente com Python 3.13/Linux: **23/23 PASS**, incluindo 32 processos concorrentes e o **teste #23 explicitamente negativo**, no qual um administrador capaz de restaurar **o próprio banco custodiado** consegue obter uma segunda emissão fictícia. Este último teste passar **significa vulnerabilidade ABERTA**, não uma garantia obtida. Rodada independente de regressão A120: **29/29 PASS**, com **5 contraexemplos intencionais**. Nenhum teste de CI/Windows ou hardware físico.

## O que o código simula e NÃO prova

1. Matrícula de intenção armazenada na fixture, fora do espelho local; campo `witness_required=0` adulterado no cliente não muda a política da fixture.
2. Identidade imutável com `owner`, `tenant`, `workspace`, `action`, `account`, hashes de conteúdo e destinatário, `idempotency` e `epoch`.
3. Uma transação `ISSUE_ONCE` é gravada antes de chamar o `FakeSender`; timeout ou resposta perdida permanecem `UNKNOWN`, sem retry. Há corrida exclusiva entre `PRE-FENCE` e `ISSUE_ONCE`.
4. Auditoria encadeada por hash e tabela de nonces são verificadas contra o cabeçalho da fixture. Falsificar/excluir linha isolada gera negação; contudo **rollback integral do próprio ledger anula esses mecanismos**.
5. A fixture nunca aceita `NO_EFFECT_FENCED` após `ISSUE_ONCE`. *ACK fictício* não comprova entrega, recebimento ou `COMMITTED_EFFECT` de fornecedor.
6. `production_enabled()` retorna sempre `False`; nenhum código de Outbox/Saga/Worker é alterado.

## Estado e dependências reais

- **H0:** qualquer emissão externa real permanece **HARD NO-GO / ZERO_AUTO_RESEND** até haver produtor com controle de credenciais separado e provas causais qualificadas.
- **F1/T1:** a autenticação da origem do checkpoint, a prova de `tenant→repo/branch/path` e a monotonicidade de restauração exigem um *trust anchor independente* do AION. Não foram construídos.
- **F2:** a autorização física HUMAN_OWNER é separada e continua pendente.
- Nenhuma conta, provedor, servidor, Worker, chaves, rede, contrato, custo, merge ou deploy habilitados.

Leia `A121_ARCHITECTURE_DECISION_AND_EXIT_GATES.md` antes de interpretar os resultados. **Nunca promover esta fixture para produção.**
