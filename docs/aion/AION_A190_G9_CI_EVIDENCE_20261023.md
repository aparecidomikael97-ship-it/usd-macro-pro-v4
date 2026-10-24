# A190 G9 — evidência CI fixada por SHA, run e jobs

**Data local de referência:** 2026-10-23 (America/Manaus). **Escopo:** PR Draft #1496 empilhada sobre G8 #1495, somente laboratório.

**SHA testado (código, testes e workflow):** 3a424b6c2c3bf08600ade212061a79cdbe30b247.

- GitHub Actions **[#40048944262](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40048944262)**: **completed / success**, dois jobs completos.
- **Ubuntu job 120736999493:** 12 tests, OK; SHA e marcadores conferidos no log.
- **Windows job 120736999647:** 12 tests, OK; SHA e marcadores conferidos no log.
- **24 testes executados** no total; cada SO executou os doze cenários com Python 3.12 e cryptography 50.0.2.
- GitHub Actions executou os binários reais dos runners; TCP, processos e SQLite são reais, porém **todos os eventos/efeitos, chaves e provedores são sintéticos**.

| Evidência observável Ubuntu + Windows | Interpretação |
| --- | --- |
| A190_G9_TWO_PINNED_SIGNATURES_VALID=SIMULATION_ONLY | Assinaturas da reserva G8 e do fornecedor sintético G9 separadas; somente matemática |
| A190_G9_REAL_PROVIDER_EFFECT_COUNT=ZERO | Nenhum fornecedor/efeito real envolvido |
| A190_G9_VENDOR_ACK_LOSS_AFTER_COMMIT=UNCERTAIN_NO_AUTO_RESEND | Resposta TCP perdida após COMMIT da simulação não desencadeia segunda tentativa |
| A190_G9_SIGNED_VENDOR_READ_ONLY_RECONCILIATION=SIMULATED_ONLY | Consulta assinada é somente evidência de registro simulado |
| A190_G9_H0_AFTER_JOURNAL_BEFORE_SEND=UNCERTAIN_NO_AUTO_RESEND | Reinício lógico entre gravação de tentativa e envio não desencadeia envio |
| A190_G9_VENDOR_DOWN_AND_RECOVERY=FAIL_CLOSED_NO_AUTO_RESEND | Falta de disponibilidade, mesmo após retorno, não abre resend automático |
| A190_G9_VENDOR_DENIES_CALLER_SIGNED_AUTHORITY_RECEIPT | Um suposto comprovante de reserva assinado pelo próprio chamador é recusado |
| A190_G9_VENDOR_FORGERY_WITH_RETAINED_PIN=DENIED | Recibo do fornecedor falsificado falha sob pin correto |
| A190_G9_SELF_PINNED_FAKE_VENDOR_RECEIPT=RED | Mesmo recibo pode verificar sob public key do atacante; NÃO é raiz confiável |
| A190_G9_PROVIDER_EFFECT_BINDING_EPOCH_EXPIRY_TAMPER=DENIED | Alteração de status, vínculo do recibo, epoch e expiração é rejeitada |
| A190_G9_CROSS_INTENT_VENDOR_RECEIPT_REUSE=DENIED | Recibo de segunda intenção não comprova a primeira |
| A190_G9_SYNTHETIC_VENDOR_REPLAY_NEW_REQUEST=DENIED | Um request-id distinto para o mesmo evento é bloqueado em SQLite íntegro |
| A190_G9_SYNTHETIC_VENDOR_CONCURRENT_SUBMISSIONS=ONE_ONLY | Seis chamadas simultâneas produzem um registro sintético |
| A190_G9_CLIENT_JOURNAL_RESET_VENDOR_STILL_DEDUPS=PASS_LAB | Journal local substituído não quebra a unicidade do fornecedor sintético íntegro |
| A190_G9_HOST_ADMIN_VENDOR_LEDGER_RESTORE=SECOND_SIGNED_SIMULATED_RECORD_RED | Administrador restaura SQLite do próprio fornecedor LAB e permite nova assinatura |
| A190_G9_TRUE_EXTERNAL_PROVIDER_IDEMPOTENCY_PROVEN=False | Contrato real de idempotência externa permanece NÃO demonstrado |

## Fronteiras não satisfeitas

- **Não houve terceiro verdadeiro:** servidor G8, cliente e fornecedor G9 estão no mesmo host runner, com chaves efêmeras sintéticas. A restauração administrativa demonstra a limitação.
- **Não houve efeito externo:** status do recibo é sempre SIMULATED_RECORD_NOT_EXTERNAL_EFFECT; não atesta envio, pagamento, usuário, corretora, cliente, fornecedor ou operação financeira.
- **Não houve custódia externa:** root/administrador pode obter acesso a chaves e SQLite de todos os papéis; logo nenhum P0 pode ser homologado com este experimento.
- **Não houve prova completa de H0/power loss:** restart lógico de objeto/processo e ACK perdido não substituem queda real de energia, durabilidade hardware e recuperação cross-host.
- **Quality/Security canônicas não reexecutadas;** cinco external-RED por SO, 43 advisories e seis P0 permanecem.
- Nenhuma contratação, conta, deploy, merge, Worker, credencial operacional ou novo gasto.

## Próximo gate real

Exigir de candidato a fornecedor/autoridade **controle administrativo realmente independente, chave publicada fora do cliente, prova de retenção antirollback, semântica de idempotência por intenção, recibo externo rastreável e reconciliação após ACK incerto**, com custo, H0 e autorização explícita do HUMAN_OWNER analisados antes de qualquer contratação. Se não houver acesso/prova, **DENY**.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND**. A contagem 24/24 refere-se SOMENTE aos testes de laboratório e inclui reproduções esperadas de falhas RED.
