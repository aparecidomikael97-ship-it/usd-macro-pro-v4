# A258 — Admissibilidade de provas independentes e contraprova do callback do Outbox (LAB)

**Estado: HARD NO-GO · 0/6 P0 homologadas · sem Worker, deploy, merge, credenciais, contratação ou efeitos reais.**

## Achado principal

A interface de `ExecutionOutbox` possui `first_attempt_guard` opcional. Sem callback, a reserva da primeira tentativa é negada. Quando fornecido, `_reserved_first_attempt` considera literalmente `True` como reserva. Isso foi uma conveniência de **simulação local** A242/A243, mas **nenhum bool controlado pelo chamador é prova de testemunha independente**. A258 contém uma **XFAIL explícita** demonstrando que `first_attempt_guard=lambda intent: True` permite o `Adapter.send` sintético da suíte A243. Isso é vulnerabilidade aberta, NÃO aprovação do P0-4.

Não modificamos o Outbox nesta PR porque os testes existentes ainda dependem deliberadamente do callback sintético; remover ou aceitar falsamente essa permissão requer migração controlada e uma interface realmente verificável de reserva. Enquanto isso, **HARD NO-GO**, Worker/deploy continuam proibidos e não existe autorização para efeitos externos.

## Contrato de admissão offline

O módulo `labs/a258_external_proof_admission.py` registra separadamente as seis obrigações:
1. HUMAN_OWNER autorizado de forma independente;
2. autoridade/custódia externa e chaves independentes;
3. event-ID legítimo imutável e proteção contra replay;
4. reserva monotônica da primeira tentativa fora do rollback do host;
5. identidade FD/VFS SQLite nativa e proteção contra rollback no mesmo inode;
6. recuperação após COMMIT e comprovante/efeito de provedor externo.

Todos os valores fornecidos pelo **próprio host** são tratados como afirmações **não verificadas**: flags `verified`, `trusted`, `ready`, `ci_passed`, certificados copiados, assinaturas sintéticas Ed25519, duas chaves locais, hashes, local WAL, notas e recibos em formato JSON. A avaliação offline **não fornece caminho positivo por desenho**: sempre `p0_homologated=0`, `authorizes_send=False`, `permits_worker=False`, `permits_deploy=False` e `permits_merge=False`. Obter provas genuinamente externas exigirá uma integração **diferente**, com verificadores de proveniência separados e testes adversariais reais. Não aceitar no futuro um simples campo booleano para promover P0.

## Ensaios A258
- 12 testes positivos de recusa: nenhum artefato, afirmações `verified`, assinatura A254, duas assinaturas vinculadas A255, nonce válido A257, 6 P0 estáveis, entrada adversarial maliciosa, resultado imutável, JSON sem autorização, 90 consultas concorrentes, Outbox sem testemunha, Outbox com função de avaliação offline.
- **13º teste (XFAIL explícita)** comprova que callback `True` ainda faz o adaptador sintético registrar envio. Não é uma exploração de serviços reais: `labs.test_a243_signed_first_attempt.Adapter` é estritamente uma fixture em memória. Entretanto prova a ausência de um gate independente nesse callback.
- Bateria Ubuntu/Windows A258/A257/A256/A255/A254/A243 e regressões de SQLite A253–A233.

## Limites e próximo trabalho

- A258 é uma **auditoria negativa executável**, não uma implementação de fornecedor independente. Não modifica `ExecutionOutbox` e **não impede** o escape do callback de testes. Manter proibição de deploy e Worker.
- Antes de qualquer operação, isolar/migrar `first_attempt_guard` de LAB para um mecanismo que verifique uma reserva de primeira tentativa em um domínio independente; exige origem válida, nonce/custódia, não-replay durável, auditoria e recibos externos.
- Provas de mesmo host não homologam nenhuma P0, mesmo quando a CI de 1000+ testes passar. **UNCERTAIN=ZERO_AUTO_RESEND**.
- Estratégia: Trader prioritário, motor econômico sob demanda para Investimentos depois, Negócios congelada/preservada, nenhum novo gasto.

**HARD NO-GO operacional.**
