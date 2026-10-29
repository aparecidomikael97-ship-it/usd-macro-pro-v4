# AION A209 — raiz de confiança alegada não é custódia independente (LAB)

**28/10/2026 · DRAFT · HARD NO-GO · 0/6 P0 homologadas**

## Por que este laboratório existe

- A207 Draft #1658 demonstrou `CONFIRMED` falso a partir de callbacks inventados (RED em Ubuntu/Windows).
- A208 Draft #1659 forneceu contrato estrutural para um futuro recibo de efeito e deixou `may_confirm=False` sempre (20/20 Ubuntu e 20/20 Windows).
- A209 trata a etapa anterior à verificação do recibo: **quem gerou, aprovou e custodía a raiz que supostamente verifica a assinatura?**

Nenhum processo pode se nomear testemunha independente apenas declarando `origin=external`, `approved=True`, configurando variável de ambiente ou escrevendo chave no próprio banco. A chave pública local e o hash declarado podem ser trocados por quem controla o host.

## Contrato implementado apenas em laboratório

`labs/a209_root_provenance_gate.py` valida um *manifesto alegado* (owner, fingerprint SHA-256, referência de cerimônia, witness, sequência, hash de checkpoint, tempo e formato de assinatura). Ele é **deny-only**:

- origem `environment`, `host_file`, `host_callback`, `runtime_generated` ou `local_database` → `ROOT_SOURCE_CONTROLLED_BY_HOST`;
- origem marcada como `claimed_external_sealed` pode ter formato coerente, mas **continua** `ROOT_STRUCTURE_OK_PROVENANCE_UNVERIFIED`;
- exige owner e pin estrutural coincidentes, rejeita sequência local repetida, hash inválido, relógio incoerente, id de testemunha vazio, campos adicionais e assinatura malformada;
- **todos os resultados** têm `independently_attested=False` e `may_confirm=False`.

O código **não** faz operações criptográficas de confiança, leitura de segredos, rede, envio, chamadas de Worker, armazenamento ou atualização da Outbox. Uma assinatura bem formada é completamente forjável; sua estrutura não comprova signatário.

## Como atingir uma raiz realmente independente

Requer uma decisão do HUMAN_OWNER e evidência externa verificável de:

1. **Cerimônia de origem e rotação de chave** supervisionada fora do host; assinatura da autorização original com identidades e tempo.
2. **Pin público imutável e auditoria de mudança de raiz** fora do mesmo domínio de escrita do Worker.
3. **Recibo causal do provedor** com chave de idempotência, intenção e escopo, verificável sem depender da palavra do adaptador.
4. **Checkpoint monotônico antirollback** mantido por testemunha independente; o parâmetro local `last_checkpoint_sequence` não serve como prova se o host pode restaurar o disco e o contador.
5. **Verificação de assinatura por biblioteca auditada**, não algoritmo criptográfico caseiro.
6. **Reprodução adversarial**: host falsificando origem, chave, assinatura, data, sequência, recibo, rollback e rotação.
7. **Aceitação independente das seis P0** antes de mudar `HARD NO-GO`.

O provedor da custódia ainda não foi escolhido. Não usar serviços ou comprar assinaturas sem autorização específica; avaliação documental sem custos pode vir a seguir.

## Testes

`labs/test_a209_root_provenance_failclosed.py` contém 18 grupos de testes sobre origem host, pin falso, owner divergente, repetição, chave trocada, JSON ambíguo e assinatura falsificada. A workflow A209 roda esse conjunto junto de A208 e regressões A206 em Ubuntu e Windows.

**Verde nesta workflow significa apenas que a negação por padrão é coerente**; não que se obteve testemunha externa. Em especial, A207 RED permanece sem correção. Nenhuma aprovação em produção é concedida.

**HARD NO-GO**. `UNCERTAIN=ZERO_AUTO_RESEND`. Sem merge, deploy, Worker, SEND real, trading, provider, credenciais, novas contas/gastos, AWS ou alterações em Negócios.
