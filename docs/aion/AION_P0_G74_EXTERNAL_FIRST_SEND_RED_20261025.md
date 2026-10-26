# AION P0-3/4 — rotas operacionais de envio sem testemunha (RED LAB)

**Data:** 25/10/2026 (America/Cuiaba). **Baseline isolada:** `77f1cfda83ab23ac9d31e63ca3749c70a4bc07e9`, G73.
**Estado:** 0/6 P0 homologados; **HARD NO-GO / ZERO_AUTO_RESEND**. Prova negativa; **não é correção** nem autorização operacional.

## Auditoria independente do Codex (somente leitura)

- Codex CLI v0.164.0-alpha.11.1; sessão `01a175d5-5f65-75f2-9b84-70711ca99729`; sandbox `read-only`, trabalho sobre cópia detached.
- Rota 1: `atlasquant_aion_admin.py:4563` chama `execute_openai_answer`; `atlasquant_aion_provider.py:435` faz POST depois de consentimento, configuração e orçamento, porém sem reserva durável de primeira tentativa. Uma falha de transporte depois da aceitação retorna `PROVIDER_NETWORK_ERROR`; nova ação manual pode gerar segundo POST.
- Rota 2: `atlasquant_neural_voice_ui.py:118-123` chama `generate_neural_speech`; `atlasquant_neural_tts.py:133` faz POST. O cache de áudio só é atualizado depois da resposta; timeout permite um segundo POST na ação seguinte.
- **Não há prova de retry automático dentro do Outbox**. `atlasquant_aion_execution_outbox.py` persiste `UNCERTAIN` antes da testemunha e mantém bloqueio por padrão. A ausência de ligação do Worker ao Outbox, isoladamente, não demonstra bypass externo nessa rota.
- Codex não alterou arquivos nem executou testes; os RED abaixo foram executados separadamente.

## Reprodução RED real (somente transporte falso)

Arquivo: `labs/a190/test_g74_operational_first_send_red_lab.py`.

```text
py -B -m unittest -v labs.a190.test_g74_operational_first_send_red_lab
Ran 4 tests in 0.001s
FAILED (failures=4)
exit code: 1
```

| Caso | Falha observada | Contrato não satisfeito |
|---|---|---|
| Texto, primeira chamada sem reserva | `1 != 0` | consentimento + orçamento não autenticam testemunha |
| Texto, ACK perdido + nova chamada | `2 not <= 1` | efeito remoto potencialmente duplicado |
| Voz, primeira chamada sem reserva | `1 != 0` | cache posterior não protege primeira tentativa |
| Voz, ACK perdido + nova chamada | `2 not <= 1` | mesma fala pode ser enviada duas vezes |

Cada POST é uma **função Python falsa** que incrementa contador e lança `TimeoutError` como se o provedor aceitasse o efeito e perdesse o ACK. **Não houve HTTP real, credencial real, custo, Worker, deploy, merge, pagamento ou modelo chamado.**

## Remediação exigida (não executada nesta PR RED)

1. Adicionar fronteira obrigatória *fail closed* ANTES dos dois POSTs; ela deve referenciar a identidade imutável do evento original e reserva única sob autoridade independente **fora do processo e host**.
2. Persistir estado `UNCERTAIN` antes de qualquer tentativa, com consulta e proteção anti-rollback. Timeout, exceção, reinício, cache perdido ou novo identificador não autorizam reenvio.
3. Expor estado de reconciliação para UI; clique posterior em resultado incerto não pode ser interpretado como primeira tentativa nova.
4. Especificar contrato de efeito e idempotência com cada provedor. Texto/voz não são ordens financeiras, mas têm efeito externo potencialmente cobrado e devem satisfazer o contrato de envio aplicável.
5. Reproduzir RED -> GREEN em Windows/Ubuntu, preservar regressões do provedor/voz existentes e executar canônicas. Nunca introduzir override controlado pelo chamador que simule uma autoridade externa.

**Decisão:** esta PR contém propositalmente **testes RED, não um patch**. Não faça merge, deploy, habilitação de Worker ou remoção dos testes para tornar CI verde. Exigir projeto de gate externo e aprovação humana antes de ligar essas rotas com prova real.
