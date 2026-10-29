# AION A211 — testemunho independente e proteção contra rollback (LAB)

**28/10/2026 · DRAFT · HARD NO-GO · 0/6 P0 externas homologadas**

## Decisão de arquitetura (ainda NÃO é escolha de fornecedor)

**Decisão A211:** manter a origem HUMAN_OWNER, a âncora monotônica de checkpoint e a validação da execução **fora do domínio administrativo do AION**. Comparações entre duas cópias de um registro não demonstram independência se um invasor puder controlar ambas. Não contratar, criar conta, criar credencial, ativar Worker ou fazer escrita externa nesta etapa.

A207 RED permanece a falha real: callbacks de adapter que dizem CONFIRMED podem ser aceitos sem prova causal externa. A208 forneceu formato de recibo sem aprovação. A209 impediu elevação por raiz autoalegada. A210 descreveu rotação sem assinatura ou ativação. A211 apenas compara amostras falsas de checkpoints, para detectar algumas anomalias que terão de ser cobertas na arquitetura real.

## Modelo de ameaça

Atacante pode controlar: host AION, código local, variáveis de ambiente, banco, timestamps, adaptadores, resposta HTTP simulada e todas as amostras entregues ao comparador A211. Ele pode reescrever duas testemunhas supostamente diferentes com o mesmo valor, falsificar observador e retornar um estado antigo perfeitamente consistente.

Objetivos futuros que exigem controles *independentes*:

1. Impedir que o host atribua autorização HUMAN_OWNER a si mesmo; a chave privada e a decisão original do proprietário ficam fora do host.
2. Detectar retorno a checkpoint antigo, falsificação de sequência, troca de raiz e divergência entre visões (fork/split view).
3. Verificar criptograficamente a inclusão de uma *declaração* em um registro externo, por meio de identidade de serviço e prova de inclusão ancoradas fora do host.
4. **Separar isso da prova de efeito real**: o ledger pode provar que um texto foi registrado, mas não que uma ordem, mensagem, cobrança ou ação externa foi concluída. Exigir evidência causal do sistema de destino, obtida de modo independente de adapter.send/reconcile e vinculada à intenção, ao nonce e à chave de idempotência.
5. Falhar fechado com serviço externo indisponível: estado UNCERTAIN e ZERO_AUTO_RESEND, sem CONFIRMED presumido e sem reenvio automático.

## Duas rotas candidatas (não provisionadas)

| Critério | Azure Confidential Ledger | Sigstore Rekor |
|---|---|---|
| Uso principal relevante | Registro append-only controlado pelo titular da assinatura Azure, com comprovantes de escrita | Registro público de transparência para metadados assinados, verificável por prova de inclusão |
| Evidência oferecida | Receipt de transação com Merkle proof, assinatura e cadeia de identidade do serviço | Entrada e inclusion proof em log, além de mecanismos de auditoria do log |
| Exigência indispensável | Verificação independente da assinatura e cadeia de confiança; custódia da âncora HUMAN_OWNER fora do AION | Verificação da assinatura do emissor, inclusão, consistência e testemunha; cuidado com a publicidade dos dados |
| Lacuna que NÃO resolve sozinho | Prova de efeito no provedor de destino; aprovação humana; origem da identidade própria | Prova de efeito no provedor de destino; aprovação humana; confidencialidade de metadados inseridos |
| Custo/decisão | Requer assinatura e eventual faturamento Azure; custo exato não autorizado nem calculado em A211 | Serviço público disponível, mas uso, privacidade, SLA e adequação precisam de decisão explícita |
| Estado A211 | Somente pesquisa documental | Somente pesquisa documental |

**Preferência de estudo:** começar por analisar formalmente Azure Confidential Ledger para dados de confirmação privados, com Rekor como referência de transparência auditável. Nenhum serviço foi escolhido, registrado ou conectado. Nunca enviar dados sensíveis para logs públicos. Uma terceira possibilidade é custódia manual offline em mídia imutável de propriedade do HUMAN_OWNER, útil como âncora de recuperação, mas não como substituto automático de receipts de execução em tempo real.

### Fontes técnicas primárias consultadas em 28/10/2026

- Microsoft — visão geral Azure Confidential Ledger: https://learn.microsoft.com/en-us/azure/confidential-ledger/overview
- Microsoft — como validar receipt, proof Merkle e assinatura: https://learn.microsoft.com/en-us/azure/confidential-ledger/verify-write-transaction-receipts
- Microsoft — autenticação de nós e rotação de identidade: https://learn.microsoft.com/en-us/azure/confidential-ledger/authenticate-ledger-nodes
- Microsoft — recibos, transações pendentes e risco de escrita duplicada após perda de resposta: https://learn.microsoft.com/en-us/azure/confidential-ledger/write-transaction-receipts
- Sigstore — transparência Rekor e monitoração de consistência: https://docs.sigstore.dev/logging/overview/
- Sigstore — verificação e recuperação de registros pelo CLI: https://docs.sigstore.dev/logging/cli/

**Inferência de engenharia:** duas amostras iguais não são duas entidades independentes sem separação real de custódia, canais e autoridade de verificação. Um hash SHA-256 isolado é apenas uma impressão digital dos bytes fornecidos.

## Laboratório sintético A211

Arquivo: labs/a211_claimed_witness_coherence.py

Entradas: checkpoint alegado do host, dois checkpoints com IDs de testemunhas declarados e o floor externo *alegado* pelo chamador. Cada entrada contém ledger, raiz, sequência, hash atual, hash parental e digest do assunto. Os observadores adicionam somente um ID alegado.

Detecta em dados sintéticos:

- Diferença de altura ou fork entre as duas testemunhas;
- Host atrás ou à frente das testemunhas;
- Inconsistência de hash e parent entre host e testemunhas;
- Retorno abaixo do floor, fork contra floor e salto de histórico sem prova;
- Troca de ledger, raiz ou assunto;
- Flags artificiais como signature_verified=True, envelopamento inesperado, observers iguais e números booleanos.

Se tudo coincide, o código retorna SHAPE_COHERENT_INDEPENDENCE_UNPROVEN, com hash canônico para comparar a **amostra**, não para confiar nela.

**Invariantes inegociáveis:**
- may_confirm=False em todos os ramos, inclusive quando structurally_coherent=True.
- Nenhuma chave, assinatura, rede, arquivo, Worker, Outbox, banco, assinatura Azure, Rekor ou alteração no estado do usuário.
- O comparador não é um verificador de Merkle proofs, certificados, identidades de testemunhas, consistência de uma árvore completa ou origem HUMAN_OWNER.
- A comparação de um único elo predecessor não comprova histórico longo: intervalos maiores que um checkpoint são rejeitados até existir prova de consistência externa.
- Copiar o MESMO histórico falso em host, floor e nas duas testemunhas ainda produz coerência de formato; não é bug, pois esse laboratório **não pode atestar independência** e jamais libera CONFIRMED.

Testes: 27 casos adversariais em labs/test_a211_claimed_witness_coherence.py. A CI A211 executa também A210, A209, A208, A206 em Linux e Windows. A207 RED não será removido nem tratado como resolvido.

## Critérios de homologação EXTERNA — todos ainda BLOQUEADOS

| P0 | Evidência necessária antes de qualquer GO |
|---|---|
| P0-1 | Intenção e raiz HUMAN_OWNER verificadas criptograficamente a partir de uma âncora física ou autoridade independente, sem autodeclaração local |
| P0-2 | Receipt autêntico, Merkle/inclusion proof e cadeia de identidades verificadas fora do host para um registro real |
| P0-3 | Confirmação causal de *efeito real* atestada pelo sistema de destino e vinculada à intenção original; não basta receipt do ledger |
| P0-4 | Âncora monotônica antirollback mantida fora do host e cenário split-view/replay controlado com evidência verificável |
| P0-5 | Testes adversariais ponta a ponta: host+DB adulterados, ack perdido, callback tardio, repetição, witness falso e falhas de rede |
| P0-6 | Aprovação específica HUMAN_OWNER da arquitetura, responsabilidade, privacidade, custo e eventual ativação operacional |

**0/6 P0 comprovados. HARD NO-GO.** A cor verde dos testes A211 só significa que a *comparação sintética* se comporta de acordo com a especificação. Não declarar P0 verde, não mascarar A207 RED, não usar flags internas para liberar operação.

## Próxima decisão humana eventual

Caso seja desejada uma prova externa real futuramente, pedir uma **autorização separada** que especifique: qual provedor ou custódia offline; conta e propriedade do recurso; escopo de dados; custos máximos e quem paga; como o HUMAN_OWNER guarda a raiz; estratégia de recuperação e ameaça de comprometimento; e a natureza do efeito externo a ser comprovado. Até lá, somente leitura, projeto e simulação offline.
