# A190 G7 — evidência remota de processos reais, assinatura Ed25519 e limites RED

**Data do checkpoint local:** 2026-10-23 (America/Manaus). **Objeto:** LAB G7, PR Draft #1494, empilhada sobre G6 #1493. **Commit de código/workflow testado:** `43ef0645cd83a2deda35365463b2b192c84640c0` (registrar este SHA mesmo após commit documental).

## Prova reproduzida no GitHub Actions

- Workflow: `.github/workflows/aion-a190-g7-os-signed-issuer-lab.yml`; Python 3.12 e `cryptography==50.0.2`. Sem acesso a provedor, conta/cliente, segredo real, deploy ou Worker.
- Run **[#40047796927](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40047796927)**: **completed / success**; dois jobs completos, nenhum erro.
- Ubuntu job **120733377382** `g7-linux-distinct-real-uid-signed-receipts`: **success**; `A190_G7_CUSTODIAN_UID=999` e `A190_G7_APP_UID=997`, processos executados sob essas identidades.
- Windows job **120733377592** `g7-windows-distinct-real-sid-signed-receipts`: **success**; SIDs reais distintos **terminados em -1004 (custodiante) e -1003 (app)**. O log de cada subprocesso contém `A190_G7_REAL_PROCESS_PRINCIPAL=` e o workflow compara o SID retornado ao SID do usuário criado.

| Invariante/contraexemplo, com evidência dos dois jobs | Resultado observado | Qualificação |
| --- | --- | --- |
| App sob UID/SID distinto tenta ler `issuer-private.raw` e abrir o SQLite do custodiante | `A190_G7_LOWER_PRIV_APP_PRIVATE_KEY=OS_DENIED`; `A190_G7_LOWER_PRIV_APP_RESERVATION_DB=OS_DENIED` | **PASS LAB**: isolamento contra app de menor privilégio |
| Custodiante assina recibo e app verifica Ed25519 sob chave publicada pelo custodiante | `A190_G7_SIGNATURE_MATH_VERIFIED_WITH_SUPPLIED_PUBLIC_KEY` | **PASS LAB**: matemática, NÃO raiz externa |
| App cria recibo falso com sua própria Ed25519 | `A190_G7_ATTEMPTED_FORGERY_REJECTED_BY_RETAINED_PIN` | **PASS LAB** sob pin retido |
| Mesmo recibo falso validado sob pin gerado pelo atacante | `A190_G7_SELF_PINNED_FAKE_KEY=MATHEMATICALLY_VALID_NOT_EXTERNAL_RED` | **RED**: auto-pin não é confiança externa |
| Segunda requisição para mesmo `original_event_id` enquanto SQLite íntegro | `A190_G7_CUSTODIAN_SAME_EVENT_NEW_REQUEST=DENIED` | **PASS LAB** somente enquanto o histórico está íntegro |
| Mesmo digest/intenção sintética sob `original_event_id` distintos, assinados | `A190_G7_DIFFERENT_SELF_CLAIMED_ORIGINAL_IDS_SAME_SEMANTIC_SHA=ADMITTED_RED` | **RED**: evento original autoalegado pode duplicar intenção |
| Root (Ubuntu) ou admin (Windows) restaura snapshot anterior do SQLite custodiante e pede outra emissão para o MESMO evento | `A190_G7_HOST_ROOT_ROLLBACK_REISSUED_ORIGINAL=UNSAFE_SIGNED_RESERVATION_RED` / `A190_G7_HOST_ADMIN_ROLLBACK_REISSUED_ORIGINAL=UNSAFE_SIGNED_RESERVATION_RED`; `req2` e `req4` assinados após restauração | **RED P0**: principal local distinto não é proteção antirollback fora do host |

**Limite dos resultados verdes:** o job deve passar precisamente porque *detecta* cada contraexemplo inseguro. A aprovação da execução NÃO indica autorização operacional, recibo confiável de fornecedor, proof-of-effect, nem conclusão dos P0.

## Primeira tentativa e correção auditável

A execução anterior **[#40047739099](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40047739099)** passou Ubuntu e falhou Windows na primeira chamada `init`: a função PowerShell `Invoke-Role` nomeava `$args`, uma variável automática do PowerShell, e perdeu os argumentos destinados à CLI (a CLI respondeu `G7 LAB usage`). Corrigimos apenas o parâmetro para `$commandArgs` e sua iteração, sem relaxar ACL, verificação de identidade ou gates; a execução posterior **#40047796927** passou integralmente. Não ocultar ou contar a execução anterior como sucesso.

## Escopo ainda NÃO comprovado

- Não há raiz de confiança fora do host, chave/pin imutável custodiado independentemente, epoch/floor monotônico protegido contra administrador, nem origem autenticada para o `original_event_id`.
- Não há recibo de provedor real, idempotência/reconciliação externa da primeira tentativa, tolerância H0 a falha de energia, cadeia de posse HUMAN_OWNER nem prova de recuperação integral após reinício.
- Não reexecutamos a Quality/Security canônicas, nem encerramos cinco external-RED por SO ou 43 advisories herdados. As provas G0–G7 são experimentos locais empilhados e não uma implantação integrada.
- A assinatura garante integridade relativa à chave pública escolhida, **não** verdade do evento, independência da custódia ou legitimidade de executar.
- `PERMITS_SEND=False` e `EXTERNAL_HOMOLOGATION=False` em cada verificação; efeito externo e reenvio seguem proibidos.

## Decisão

**0/6 P0 HOMOLOGADOS. HARD NO-GO. UNCERTAIN. ZERO_AUTO_RESEND.**

A PR deve ficar **Draft**, isolada sobre #1493. **Sem merge/main, deploy, Worker, integração financeira, autenticação operacional ou contratação**. Próximo gate de engenharia: especificar autoridade de emissão e evento original com raiz/rollback fora do domínio de administração do próprio host, contemplando falha da autoridade (`DENY`) e confirmação externa antes de qualquer efeito. Não escolher nem provisionar serviço externo sem decisão fundamentada do proprietário e análise do teto R$200/mês (exceção R$250 somente com autorização).
