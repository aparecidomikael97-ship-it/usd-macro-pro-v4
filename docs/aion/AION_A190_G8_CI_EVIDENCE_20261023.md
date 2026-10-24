# A190 G8 — evidência CI remota e qualificação do protocolo simulado

**Data local:** 2026-10-23 (America/Manaus). **LAB Draft #1495**, sobre G7 #1494. **Código + testes + workflow testados no SHA 3386943e81f7d81d3c052ecd506767b0edcf9cb0.**

## Execução real

- [GitHub Actions run #40048413834](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40048413834): **completed / success**.
- **Ubuntu:** job **120735316328**, 10 testes / 10 aprovados, Python 3.12 com cryptography 50.0.2.
- **Windows:** job **120735316013**, 10 testes / 10 aprovados, Python 3.12 com cryptography 50.0.2.
- **Total observado:** 20 execuções individuais concluídas nos dois SOs. Os testes rodaram de fato em CI e os logs por job contêm os marcadores abaixo. Nenhum provedor externo de efeito foi exercido.

| Caso verificado em Ubuntu e Windows | Marcador objetivo | Resultado interpretado |
| --- | --- | --- |
| TCP 127.0.0.1 com custodiante em processo separado, SQLite + Ed25519 | A190_G8_REAL_INTERPROCESS_ED25519_RESERVE=PASS_LAB | **PASS LAB**, processo real mas não host independente |
| Mesmo evento semântico, outro request e ID alegado pelo cliente | A190_G8_SAME_SEMANTIC_DIFFERENT_REQUEST_AND_CLAIMED_ID=DENIED | **PASS LAB**, UNIQUE por digest semanticamente assinado |
| Duas referências de eventos originais válidas, mesma intenção semântica | A190_G8_SIGNED_ALTERNATE_ORIGINAL_SAME_SEMANTIC=DENIED_LAB | **PASS LAB**, desde que emissor original seja confiável |
| Emissor falso / payload original adulterado | A190_G8_UNTRUSTED_EVENT_SOURCE_PIN_AND_POST_SIGN_MUTATION=DENIED | **PASS LAB**, pin da fonte fixado na configuração do custodiante |
| TCP corta resposta após reserva SQLite gravada | A190_G8_TCP_REPLY_DROPPED_AFTER_COMMIT=UNCERTAIN_ZERO_AUTO_RESEND | **PASS LAB**, sem retentativa automática |
| Consulta posterior somente leitura não confirma efeito externo | A190_G8_READ_ONLY_RECONCILIATION=RESERVED_NOT_EFFECT_CONFIRMED | **PASS LAB**, não é recibo de fornecedor |
| Estado local do cliente é esquecido/substituído | A190_G8_CLIENT_ONLY_ROLLBACK_SERVER_RETAINED=DENY_DUPLICATE | **PASS LAB**, reserva fica no estado do processo custodiante |
| Servidor indisponível/fora do ar | A190_G8_H0_AUTHORITY_UNAVAILABLE=NO_NEW_EFFECT_NO_AUTO_RESEND | **PASS LAB**, cliente falha fechado |
| Admin do host repõe SQLite do custodiante de antes da reserva | A190_G8_SAME_HOST_ADMIN_REMOTE_STATE_RESTORE=UNSAFE_RESIGN_RED | **RED**, restauração permite segunda assinatura válida |
| Pin falso, epoch errado, recibo vencido, estado EFFECT_CONFIRMED forjado | A190_G8_PIN_EPOCH_EXPIRY_EFFECT_FORGERY=DENIED_WITH_RETAINED_PIN | **PASS LAB** sob pin honesto retido; auto-pin continua RED |
| Seis solicitações concorrentes para mesma intenção | A190_G8_REAL_TCP_SQLITE_CONCURRENT_SAME_SEMANTIC=ONE_ONLY | **PASS LAB** 1 aceita, 5 negadas |
| Consulta reserva sem comprovante de efeito | A190_G8_NO_PROVIDER_RECEIPT_NO_EFFECT_CONFIRMED=ENFORCED_LAB | **PASS LAB**, jamais tratar como entrega/ordem executada |

## O que a execução NÃO homologa

1. **Separação de hosts/operadores ou resistência real ao administrador.** É processo separado no mesmo host e o teste demonstra explicitamente o bypass ao restaurar o banco do custodiante. Diretório e chave da simulação são acessíveis a admin/root.
2. **Autenticidade operacional de evento ou HUMAN_OWNER.** O emissor original e os pins foram gerados pelo próprio ensaio. O cliente não está associado a credencial de produção/usuário e não houve aprovação biométrica.
3. **Efeito real ou fornecedor.** O recibo representa SOMENTE reserva sintética; nenhuma operação externa, pagamento, reenvio ou integração.
4. **Sobrevivência a power-loss real ou H0 homologado.** Parada de processo foi exercida; queda de energia, armazenamento independente, clock e falhas distribuídas não foram certificados.
5. **Segurança/Quality canônicas e dívida histórica.** Não reexecutadas aqui; cinco external-RED por SO e 43 advisories permanecem pendentes. Nada fecha os seis P0.

## Decisão auditável

- O contrato de unicidade por evento ORIGINAL assinado melhora a modelagem e elimina o bypass trivial de mudar IDs em **estado íntegro**; isso depende de uma fonte verdadeira e independente, ainda **não existente**.
- Uma autoridade que apenas executa noutro processo/serviço do **mesmo computador** falha contra o rollback por administrador; selecionar uma arquitetura B/C externa exige prova de controle administrativo independente, disponibilidade H0, comprovante de fornecedor e custo verificado.
- Consulta somente leitura pode explicar que uma reserva foi persistida, jamais implicar execução ou autorizar reenvio.
- A PR permanece **Draft, empilhada e não integrada**. Nada foi implantado/contratado; custo incremental do ensaio além dos recursos preexistentes não foi solicitado.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**
