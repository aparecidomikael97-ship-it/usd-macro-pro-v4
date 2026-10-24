# A190 G3 — primeira intenção, identificador original e resultado incerto

**Data de referência:** 2026-10-23, fuso do proprietário. **Estado:** somente LAB/Draft, não homologado, sem efeito externo. Missão #1486. Base empilhada A190 G2 PR #1489.

## Escopo verificável

Esta rodada conecta **os módulos já existentes**, sem modificar o código de execução AION:

- `aion_chat/external_authority_a183_lab.py` — verificação Ed25519 por papéis/challenge, com chaves, raiz e sequência ainda sintéticas e fornecidas pelo chamador.
- `labs/a189/local_witness_failclosed_lab.py` — reserva de request/event ID em SQLite e witness local; gera `UNCERTAIN` em perda sintética de ACK, com `auto_resend=False`.
- `test_atlasquant_aion_a190_g3_first_intent_contract_lab.py` — seis experimentos integrados entre A183/A189, com chaves, tenants, eventos e intenções inteiramente artificiais. Não há chamadas de rede, nenhum fornecedor, chave real, cliente, Worker ou envio.
- `.github/workflows/aion-a190-g3-first-intent-lab.yml` — execução Ubuntu e Windows de G3 e das suítes A183/A189 herdadas; resultados devem ser identificados por **run ID, SHA e logs reais**, não presumidos.

## Hipóteses e critérios predefinidos

| Caso | Controle positivo / negativo | Resultado esperado do LAB | Interpretação de segurança |
| --- | --- | --- | --- |
| G3-1 | Mesmo `event_id` e outro `request_id` | A183 nega replay no objeto e A189 nega segunda reserva do mesmo ID | Proteção apenas local e **sobre ID autoalegado**; insuficiente para P0 |
| G3-2 | **Mesma intenção sintética**, mesmo `original_sha256`, IDs de evento distintos, novos desafios e assinaturas A183 válidas | Duas autorizações LAB/duas reservas SQLite locais aceitas | **RED:** assinatura válida não atesta que IDs diferentes representem operações distintas |
| G3-3 | Atacante substitui as chaves sintéticas, `pins` e raiz esperada; cria `RECEIPT` com Ed25519 legítimo para suas próprias chaves | Verificador com raiz original rejeita; novo verificador *self-pinned* aceita | **RED:** nenhuma raiz independente persistente. `lab_verified` não autentica fornecedor |
| G3-4 | ACK perdido após reserva; mesmo ID/novo request; depois outro `event_id` autoalegado | `UNCERTAIN`/sem reenvio para primeiro caso; novo ID é reservado | **RED:** nem `ZERO_AUTO_RESEND` local impede um novo pedido semanticamente duplicado com identificador falso |
| G3-5 | Recibo ausente/timeout e recibo assinado por fixture | Timeout recusa; fixture retorna `permits_send=False`, `permits_retry=False`, `external_homologation=False` | Sem prova do efeito do fornecedor |
| G3-6 | Callback não confiável executa ação **somente em memória** antes de retornar evidência inválida | Verificador rejeita o documento, mas efeito em memória já ocorreu | **RED de fronteira:** consulta de evidência não pode ser encarregada de disparar efeito |

**Nota de modelagem:** não fazer unicidade global somente por `payload_hash` — duas operações comerciais legítimas podem ter conteúdo idêntico. O oráculo destes testes conhece a mesma intenção sintética. A solução exige a **identidade estável e autenticada do evento original por uma autoridade fora do aplicativo**, escopo/tenant/tipo de operação e o contrato de idempotência do autorizador/fornecedor. Distintos `request_id` jamais significam, por si, distintas primeiras tentativas.

## Protocolo de produção ainda NÃO comprovado — condição G3

1. Um principal de origem independente emite `original_event_id` imutável, vinculado a contexto, escopo, tenant, intenção canônica e identidade autorizada; o AION não pode escolher/trocar esse identificador, sua chave, raiz ou epoch.
2. O custodiante independente faz CAS da **primeira** reserva por chave semântica derivada de evento original autenticado + operação + escopo. A operação não avança se a raiz, piso, desafio, revogação ou reserva não estiverem disponíveis ou coerentes.
3. Somente um autorizador de efeito com contrato de idempotência verificável decide a primeira tentativa e o estado do efeito. Perda de ACK, timeout, crash e recuperação parcial não autorizam reenvio automático nem segunda intenção por novo `request_id`.
4. Reconciliação usa leitura autenticada do fornecedor/custodiante e recibo atribuível ao principal do efeito, com epoch, nonce, chave de idempotência e transação vinculados à primeira reserva. Autoassinatura, JSON local e `lab_verified` **não** são recibo independente.
5. Se a consulta não concluir: manter `UNCERTAIN` e **`ZERO_AUTO_RESEND`**, preservar o bloqueio de nova operação e escalar para análise humana. Não inferir sucesso de `ALREADY_RESERVED_LOCAL` ou de contador SQLite.

## Limitações incontornadas nesta PR

- Nenhuma assinatura ou recibo de **emissor independente real**, nem credencial, API, custódia monotônica externa, semântica comprovada de exatamente-uma-vez ou identidade HUMAN_OWNER por FIDO2/Windows Hello.
- Não reproduz crash real com efeito externo nem isolamento de principal do fornecedor, nem rollback conjunto real da operação. A183/A189 são laboratórios e não integram um autorizador operacional.
- A184 Quality/Security canônicas **não são reexecutadas por este workflow**. Permanecem herdados **cinco external-RED por SO** e **43 advisories** até evidência específica. A190 G2 permanece vulnerável a restauração root/admin no mesmo host; SQLite nativo LIVE, WAL/SHM, FD/VFS, ABA, H0 e power loss ainda não homologados.
- Os controles negativos servem para negar afirmações de segurança, não para habilitar nova operação. Não marcar G3 verde porque os testes de bypass passaram.

## Evidência e decisão pendente

- PR Draft para ensaio G3: criar sobre #1489 e registrar run ID/SHA/logs de Ubuntu e Windows. **CI pendente no momento da criação deste documento.**
- Para prosseguir com *prova externa real*, é necessária escolha e autorização específicas de uma autoridade/custodiante e fornecedor, análise do contrato técnico (idempotência, ACK incerto, revogação, retenção, auditoria), preços e identidade operacional. **Nenhuma contratação, gasto ou credencial real foi aprovada neste bloco**; teto de R$200/mês permanece, até R$250 apenas com autorização expressa e justificativa.
- **Status global: 0/6 P0 homologados; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND. Sem merge, deploy, main, Worker, efeitos reais ou mudança de gates.**
